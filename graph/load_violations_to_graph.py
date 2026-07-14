"""
从 JSON 文件加载电子设计违例知识到 Graphiti 图数据库

节点和边均通过 Graphiti 创建，保持与后续 search/traverse 等功能的兼容性。
边的语义类型存储在 EntityEdge.name 属性中（has_phenomenon / has_root_cause）。
在 Neo4j 浏览器中可执行 :style relationship RELATES_TO { caption: '{name}'; } 显示边类型。

JSON 格式:
{
  "nodes": [
    {"id": "...", "type": "ViolationConcept", "properties": {...}},
    {"id": "...", "type": "Phenomenon",       "properties": {...}},
    {"id": "...", "type": "RootCause",         "properties": {...}}
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

from custom_llm_client import ThinkTagCleaningClient

os.environ['GRAPHITI_TELEMETRY_ENABLED'] = 'false'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

neo4j_uri = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
neo4j_user = os.environ.get('NEO4J_USER', 'neo4j')
neo4j_password = os.environ.get('NEO4J_PASSWORD', 'password')

local_llm_base_url = os.environ.get('LOCAL_LLM_BASE_URL', 'http://localhost:8000/v1')
local_llm_model = os.environ.get('LOCAL_LLM_MODEL', 'qwen2.5')
local_llm_api_key = os.environ.get('LOCAL_LLM_API_KEY', 'dummy-key')

local_embed_base_url = os.environ.get('LOCAL_EMBED_BASE_URL', 'http://localhost:8001/v1')
local_embed_api_key = os.environ.get('LOCAL_EMBED_API_KEY', 'dummy-key')

ALLOWED_RELATIONS = {'has_phenomenon', 'has_root_cause'}


async def load_nodes(graphiti: Graphiti, nodes_data: list[dict]) -> dict[str, str]:
    """加载所有节点，返回 json_id -> node_uuid 映射"""
    id_to_uuid = {}

    logger.info(f"加载 {len(nodes_data)} 个节点...\n")

    for node_data in nodes_data:
        node_id = node_data['id']
        node_type = node_data['type']
        properties = node_data.get('properties', {})

        if node_type == 'ViolationConcept':
            name = properties.get('name', node_id)
            attributes = {
                'automation_difficulty': properties.get('automation_difficulty', ''),
                'remarks': properties.get('remarks', ''),
                'source_id': node_id,
            }
            summary = f"[{node_type}] {name}"
            if attributes['remarks']:
                summary += f" — {attributes['remarks']}"

        elif node_type == 'Phenomenon':
            name = properties.get('name', node_id)
            attributes = {
                'identification_method': properties.get('identification_method', ''),
                'source_id': node_id,
            }
            summary = f"[{node_type}] {name}: {attributes['identification_method']}"

        elif node_type == 'RootCause':
            name = properties.get('scenario_id', node_id)
            attributes = {
                'scenario_id': properties.get('scenario_id', ''),
                'analysis_action': properties.get('analysis_action', ''),
                'fix_method': properties.get('fix_method', ''),
                'dependent_tool': properties.get('dependent_tool', ''),
                'source_id': node_id,
            }
            summary = (
                f"[{node_type}] {name}"
                f" | 排查: {attributes['analysis_action']}"
                f" | 修复: {attributes['fix_method']}"
            )

        else:
            logger.warning(f"  ⚠ 未知节点类型: {node_type}, 跳过节点 {node_id}")
            continue

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
        logger.info(f"  ✓ [{node_type}] {node_id} → '{name}' (uuid: {node.uuid[:8]}...)")

        id_to_uuid[node_id] = node.uuid

    logger.info("")
    return id_to_uuid


async def load_edges(graphiti: Graphiti, edges_data: list[dict], id_to_uuid: dict[str, str]):
    """通过 Graphiti EntityEdge 加载边，name 属性存储关系语义"""
    logger.info(f"加载 {len(edges_data)} 条边...\n")

    for edge_data in edges_data:
        source_id = edge_data['source']
        target_id = edge_data['target']
        relation = edge_data['relation']

        if relation not in ALLOWED_RELATIONS:
            logger.warning(f"  ⚠ 跳过边: 不支持的关系类型 '{relation}'")
            continue

        source_uuid = id_to_uuid.get(source_id)
        target_uuid = id_to_uuid.get(target_id)

        if source_uuid is None:
            logger.warning(f"  ⚠ 跳过: source '{source_id}' 未找到")
            continue
        if target_uuid is None:
            logger.warning(f"  ⚠ 跳过: target '{target_id}' 未找到")
            continue

        if relation == 'has_phenomenon':
            fact = f'{source_id} 的现象识别方法对应 {target_id}'
        else:
            fact = f'{source_id} 的根因包含 {target_id}'

        edge = EntityEdge(
            uuid=str(uuid4()),
            source_node_uuid=source_uuid,
            target_node_uuid=target_uuid,
            name=relation,                     # has_phenomenon / has_root_cause
            fact=fact,
            group_id='default',
            created_at=datetime.now(timezone.utc),
            valid_at=datetime.now(timezone.utc),
            attributes={
                'source_id': source_id,
                'target_id': target_id,
            },
        )

        await graphiti.edges.entity.save(edge)
        logger.info(f"  ✓ {source_id} --[{relation}]--> {target_id}")

    logger.info("")


async def main():
    json_file_path = "violations_data.json"

    if not os.path.exists(json_file_path):
        logger.error(f"❌ JSON 文件不存在: {json_file_path}")
        return

    logger.info("=" * 60)
    logger.info("开始加载违例知识到图数据库")
    logger.info("=" * 60)

    os.environ['SEMAPHORE_LIMIT'] = '3'

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

    logger.info("初始化 Graphiti...")
    graphiti = Graphiti(
        neo4j_uri, neo4j_user, neo4j_password,
        llm_client=llm_client,
        embedder=embedder,
    )

    try:
        logger.info(f"读取 JSON 文件: {json_file_path}")
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        nodes_data = data.get('nodes', [])
        edges_data = data.get('edges', [])
        logger.info(f"节点数: {len(nodes_data)}, 边数: {len(edges_data)}\n")

        id_to_uuid = await load_nodes(graphiti, nodes_data)
        await load_edges(graphiti, edges_data, id_to_uuid)

        logger.info("=" * 60)
        logger.info("✅ 加载完成！")
        logger.info("💡 Neo4j 浏览器中执行以下命令可显示边的语义类型:")
        logger.info("   :style relationship RELATES_TO { caption: '{name}'; }")
        logger.info("=" * 60)

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON 解析错误: {e}")
    except Exception as e:
        logger.error(f"❌ 发生错误: {e}", exc_info=True)
    finally:
        await graphiti.close()
        logger.info("✓ 连接已关闭")


if __name__ == '__main__':
    asyncio.run(main())
