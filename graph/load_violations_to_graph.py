"""
从 JSON 文件加载电子设计违例知识到 Graphiti 图数据库
"""
import asyncio
import json
import os
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from uuid import uuid4

from graphiti_core import Graphiti
from graphiti_core.nodes import EntityNode
from graphiti_core.edges import EntityEdge
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig

# 导入自定义的清理 think 标签的 Client
from custom_llm_client import ThinkTagCleaningClient

# 禁用遥测
os.environ['GRAPHITI_TELEMETRY_ENABLED'] = 'false'

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 加载 .env 文件
load_dotenv()

# 从环境变量读取配置
neo4j_uri = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
neo4j_user = os.environ.get('NEO4J_USER', 'neo4j')
neo4j_password = os.environ.get('NEO4J_PASSWORD', 'password')

local_llm_base_url = os.environ.get('LOCAL_LLM_BASE_URL', 'http://localhost:8000/v1')
local_llm_model = os.environ.get('LOCAL_LLM_MODEL', 'qwen2.5')
local_llm_api_key = os.environ.get('LOCAL_LLM_API_KEY', 'dummy-key')

local_embed_base_url = os.environ.get('LOCAL_EMBED_BASE_URL', 'http://localhost:8001/v1')
local_embed_api_key = os.environ.get('LOCAL_EMBED_API_KEY', 'dummy-key')


async def create_or_get_node(graphiti: Graphiti, name: str, labels: list, summary: str,
                             attributes: dict = None, group_id: str = "default") -> EntityNode:
    """创建或获取节点（如果已存在则复用）"""
    try:
        # 尝试获取已存在的节点
        existing = await graphiti.nodes.entity.get(name=name, group_id=group_id)
        if existing:
            logger.info(f"  ✓ 节点已存在: {name}")
            return existing[0]
    except:
        pass

    # 创建新节点
    node = EntityNode(
        uuid=str(uuid4()),
        name=name,
        labels=labels,
        summary=summary,
        group_id=group_id,
        created_at=datetime.now(timezone.utc)
    )

    if attributes:
        node.attributes = attributes

    await graphiti.nodes.entity.save(node)
    logger.info(f"  ✓ 创建节点: {name} [{', '.join(labels)}]")
    return node


async def create_edge(graphiti: Graphiti, source_uuid: str, target_uuid: str,
                     relation_type: str, fact: str, group_id: str = "default"):
    """创建关系边"""
    edge = EntityEdge(
        uuid=str(uuid4()),
        source_node_uuid=source_uuid,
        target_node_uuid=target_uuid,
        name=relation_type,
        fact=fact,
        group_id=group_id,
        created_at=datetime.now(timezone.utc),
        valid_at=datetime.now(timezone.utc)
    )

    await graphiti.edges.entity.save(edge)
    logger.info(f"    → 创建关系: {relation_type}")


async def load_violation_from_json(graphiti: Graphiti, violation_data: dict, group_id: str = "default"):
    """
    从单条违例数据构建图结构

    预期 JSON 格式:
    {
        "violation_concept": "违例概念名称",
        "symptom_method": "现象识别方法描述",
        "root_causes": [
            {
                "cause": "根因1描述",
                "analysis_action": "排查动作1",
                "fix_method": "修复方法1",
                "tools": ["工具A", "工具B"]
            },
            ...
        ],
        "detection_tools": ["检测工具1", "检测工具2"]
    }
    """
    violation_concept = violation_data['violation_concept']
    symptom_method = violation_data['symptom_method']
    root_causes = violation_data.get('root_causes', [])
    detection_tools = violation_data.get('detection_tools', [])

    logger.info(f"\n处理违例: {violation_concept}")

    # 1. 创建违例概念节点
    violation_node = await create_or_get_node(
        graphiti,
        name=violation_concept,
        labels=["Violation"],
        summary=f"电子设计违例类型: {violation_concept}",
        attributes={"category": "design_violation"},
        group_id=group_id
    )

    # 2. 创建现象识别方法节点
    symptom_node = await create_or_get_node(
        graphiti,
        name=f"Symptom_{violation_concept}",
        labels=["Symptom", "DetectionMethod"],
        summary=symptom_method,
        attributes={"method": symptom_method},
        group_id=group_id
    )

    # 连接: Violation -> Symptom
    await create_edge(
        graphiti,
        source_uuid=violation_node.uuid,
        target_uuid=symptom_node.uuid,
        relation_type="HAS_SYMPTOM",
        fact=f"{violation_concept} 的识别方法是: {symptom_method}",
        group_id=group_id
    )

    # 3. 创建检测工具节点并连接
    for tool_name in detection_tools:
        tool_node = await create_or_get_node(
            graphiti,
            name=tool_name,
            labels=["Tool", "DetectionTool"],
            summary=f"检测工具: {tool_name}",
            group_id=group_id
        )

        await create_edge(
            graphiti,
            source_uuid=symptom_node.uuid,
            target_uuid=tool_node.uuid,
            relation_type="REQUIRES_TOOL",
            fact=f"{symptom_method} 需要使用工具 {tool_name}",
            group_id=group_id
        )

    # 4. 处理每个根因及其对应的修复方法
    for idx, root_cause_data in enumerate(root_causes):
        cause_desc = root_cause_data['cause']
        analysis_action = root_cause_data.get('analysis_action', '')
        fix_method = root_cause_data['fix_method']
        tools = root_cause_data.get('tools', [])

        logger.info(f"  处理根因 {idx+1}: {cause_desc}")

        # 创建根因节点
        cause_node = await create_or_get_node(
            graphiti,
            name=f"RootCause_{violation_concept}_{idx+1}",
            labels=["RootCause"],
            summary=cause_desc,
            attributes={
                "cause": cause_desc,
                "analysis_action": analysis_action
            },
            group_id=group_id
        )

        # 连接: Symptom -> RootCause
        await create_edge(
            graphiti,
            source_uuid=symptom_node.uuid,
            target_uuid=cause_node.uuid,
            relation_type="MAY_CAUSE",
            fact=f"{violation_concept} 可能由以下原因引起: {cause_desc}",
            group_id=group_id
        )

        # 创建修复方法节点
        fix_node = await create_or_get_node(
            graphiti,
            name=f"Fix_{violation_concept}_{idx+1}",
            labels=["Fix", "Solution"],
            summary=fix_method,
            attributes={"method": fix_method},
            group_id=group_id
        )

        # 连接: RootCause -> Fix (一对一)
        await create_edge(
            graphiti,
            source_uuid=cause_node.uuid,
            target_uuid=fix_node.uuid,
            relation_type="FIXED_BY",
            fact=f"{cause_desc} 的修复方法是: {fix_method}",
            group_id=group_id
        )

        # 创建修复工具节点并连接
        for tool_name in tools:
            tool_node = await create_or_get_node(
                graphiti,
                name=tool_name,
                labels=["Tool", "FixTool"],
                summary=f"修复工具: {tool_name}",
                group_id=group_id
            )

            await create_edge(
                graphiti,
                source_uuid=fix_node.uuid,
                target_uuid=tool_node.uuid,
                relation_type="REQUIRES_TOOL",
                fact=f"{fix_method} 需要使用工具 {tool_name}",
                group_id=group_id
            )


async def main():
    """主函数"""
    # JSON 文件路径
    json_file_path = "violations_data.json"

    if not os.path.exists(json_file_path):
        logger.error(f"❌ JSON 文件不存在: {json_file_path}")
        logger.info("请先创建 violations_data.json 文件")
        return

    logger.info("=" * 60)
    logger.info("开始加载违例知识到图数据库")
    logger.info("=" * 60)

    # 降低并发限制
    os.environ['SEMAPHORE_LIMIT'] = '3'

    # 配置 LLM 和 Embedding
    llm_config = LLMConfig(
        api_key=local_llm_api_key,
        model=local_llm_model,
        base_url=local_llm_base_url,
    )

    llm_client = ThinkTagCleaningClient(
        config=llm_config,
        structured_output_mode="json_object"
    )

    embedder_config = OpenAIEmbedderConfig(
        api_key=local_embed_api_key,
        base_url=local_embed_base_url,
        embedding_model="BAAI/bge-m3",
        embedding_dim=1024
    )
    embedder = OpenAIEmbedder(config=embedder_config)

    # 初始化 Graphiti
    logger.info("初始化 Graphiti...")
    graphiti = Graphiti(
        neo4j_uri,
        neo4j_user,
        neo4j_password,
        llm_client=llm_client,
        embedder=embedder,
    )

    try:
        # 读取 JSON 文件
        logger.info(f"读取 JSON 文件: {json_file_path}")
        with open(json_file_path, 'r', encoding='utf-8') as f:
            violations_data = json.load(f)

        # 支持单个对象或对象数组
        if isinstance(violations_data, dict):
            violations_list = [violations_data]
        else:
            violations_list = violations_data

        logger.info(f"共加载 {len(violations_list)} 条违例数据\n")

        # 逐条处理违例数据
        for idx, violation in enumerate(violations_list, 1):
            logger.info(f"[{idx}/{len(violations_list)}] 处理中...")
            await load_violation_from_json(graphiti, violation)
            logger.info(f"[{idx}/{len(violations_list)}] 完成\n")

        logger.info("=" * 60)
        logger.info("✅ 所有数据加载完成！")
        logger.info("=" * 60)

    except FileNotFoundError:
        logger.error(f"❌ 找不到文件: {json_file_path}")
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON 解析错误: {e}")
    except Exception as e:
        logger.error(f"❌ 发生错误: {e}", exc_info=True)
    finally:
        await graphiti.close()
        logger.info("✓ 连接已关闭")


if __name__ == '__main__':
    asyncio.run(main())
