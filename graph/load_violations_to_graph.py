"""
从 JSON 文件加载电子设计违例知识到 Graphiti 图数据库

JSON 格式:
{
  "nodes": [
    {"id": "...", "type": "ViolationConcept", "properties": {"name": "...", "automation_difficulty": "...", "remarks": "..."}},
    {"id": "...", "type": "Phenomenon",       "properties": {"name": "...", "identification_method": "..."}},
    {"id": "...", "type": "RootCause",         "properties": {"scenario_id": "...", "analysis_action": "...", "fix_method": "...", "dependent_tool": "..."}}
  ],
  "edges": [
    {"source": "v_xxx", "target": "p_xxx", "relation": "has_phenomenon"},
    {"source": "p_xxx", "target": "r_xxx", "relation": "has_root_cause"}
  ]
}
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


async def load_nodes(graphiti: Graphiti, nodes_data: list[dict]) -> dict[str, str]:
    """
    加载所有节点，返回 json_id -> node_uuid 的映射

    支持三种节点类型:
    - ViolationConcept: name, automation_difficulty, remarks
    - Phenomenon:       name, identification_method
    - RootCause:         scenario_id, analysis_action, fix_method, dependent_tool
    """
    id_to_uuid = {}

    logger.info(f"加载 {len(nodes_data)} 个节点...\n")

    for node_data in nodes_data:
        node_id = node_data['id']
        node_type = node_data['type']
        properties = node_data['properties']

        # 根据不同类型提取字段
        if node_type == 'ViolationConcept':
            name = properties['name']
            automation_difficulty = properties.get('automation_difficulty', '')
            remarks = properties.get('remarks', '')

            summary = f"[{node_type}] {name}"
            if remarks:
                summary += f" - {remarks}"

            attributes = {
                'automation_difficulty': automation_difficulty,
                'remarks': remarks,
            }

        elif node_type == 'Phenomenon':
            name = properties['name']
            identification_method = properties.get('identification_method', '')

            summary = f"[{node_type}] {name}"
            if identification_method:
                summary += f" - 识别方法: {identification_method}"

            attributes = {
                'identification_method': identification_method,
            }

        elif node_type == 'RootCause':
            name = properties['scenario_id']  # 用 scenario_id 作为节点名称
            scenario_id = properties.get('scenario_id', '')
            analysis_action = properties.get('analysis_action', '')
            fix_method = properties.get('fix_method', '')
            dependent_tool = properties.get('dependent_tool', '')

            summary = f"[{node_type}] 场景 {scenario_id}: {analysis_action}"

            attributes = {
                'scenario_id': scenario_id,
                'analysis_action': analysis_action,
                'fix_method': fix_method,
                'dependent_tool': dependent_tool,
            }

        else:
            logger.warning(f"  ⚠ 未知节点类型: {node_type}, 跳过节点 {node_id}")
            continue

        # 创建节点
        node = EntityNode(
            uuid=str(uuid4()),
            name=name,
            labels=[node_type],
            summary=summary,
            group_id='default',
            created_at=datetime.now(timezone.utc),
        )

        if attributes:
            node.attributes = attributes

        await graphiti.nodes.entity.save(node)
        logger.info(f"  ✓ [{node_type}] {node_id} → {name} (uuid: {node.uuid[:8]}...)")

        # 记录映射
        id_to_uuid[node_id] = node.uuid

    logger.info("")
    return id_to_uuid


async def load_edges(graphiti: Graphiti, edges_data: list[dict], id_to_uuid: dict[str, str]):
    """根据映射表加载所有边"""
    logger.info(f"加载 {len(edges_data)} 条边...\n")

    for edge_data in edges_data:
        source_id = edge_data['source']
        target_id = edge_data['target']
        relation = edge_data['relation']

        # 通过映射表获取实际 UUID
        source_uuid = id_to_uuid.get(source_id)
        target_uuid = id_to_uuid.get(target_id)

        if source_uuid is None:
            logger.warning(f"  ⚠ 跳过边: source {source_id} 未找到")
            continue
        if target_uuid is None:
            logger.warning(f"  ⚠ 跳过边: target {target_id} 未找到")
            continue

        # 构建语义化 fact 描述
        if relation == 'has_phenomenon':
            fact = f'{source_id} 的现象识别方法对应 {target_id}'
        elif relation == 'has_root_cause':
            fact = f'{source_id} 的根因包含 {target_id}'
        else:
            fact = f'{source_id} --[{relation}]--> {target_id}'

        edge = EntityEdge(
            uuid=str(uuid4()),
            source_node_uuid=source_uuid,
            target_node_uuid=target_uuid,
            name=relation,
            fact=fact,
            group_id='default',
            created_at=datetime.now(timezone.utc),
            valid_at=datetime.now(timezone.utc),
        )

        await graphiti.edges.entity.save(edge)
        logger.info(f"  ✓ {source_id} --[{relation}]--> {target_id}")

    logger.info("")


async def main():
    """主函数"""
    # JSON 文件路径
    json_file_path = "violations_data.json"

    if not os.path.exists(json_file_path):
        logger.error(f"❌ JSON 文件不存在: {json_file_path}")
        logger.info("请先创建 violations_data.json 文件，格式参考 violations_data_example.json")
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
            data = json.load(f)

        nodes_data = data.get('nodes', [])
        edges_data = data.get('edges', [])

        logger.info(f"节点数: {len(nodes_data)}, 边数: {len(edges_data)}\n")

        # 1. 加载节点，获取 id → uuid 映射
        id_to_uuid = await load_nodes(graphiti, nodes_data)

        # 2. 加载边
        await load_edges(graphiti, edges_data, id_to_uuid)

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
