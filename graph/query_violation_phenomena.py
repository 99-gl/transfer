"""根据查询词查找违例节点，并通过 Graphiti 返回其关联的所有现象节点。

用法：
    python query_violation_phenomena.py "Setup Time Violation"
"""
import argparse
import asyncio
import logging
import os

from dotenv import load_dotenv

from graphiti_core import Graphiti
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client.config import LLMConfig

from custom_llm_client import ThinkTagCleaningClient


os.environ['GRAPHITI_TELEMETRY_ENABLED'] = 'false'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
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
local_embed_model = os.environ.get('LOCAL_EMBED_MODEL', 'BAAI/bge-m3')


def create_graphiti() -> Graphiti:
    """使用与图谱加载脚本相同的客户端配置初始化 Graphiti。"""
    llm_config = LLMConfig(
        api_key=local_llm_api_key,
        model=local_llm_model,
        base_url=local_llm_base_url,
    )
    llm_client = ThinkTagCleaningClient(
        config=llm_config,
        structured_output_mode='json_object',
    )
    embedder = OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key=local_embed_api_key,
            base_url=local_embed_base_url,
            embedding_model=local_embed_model,
        )
    )
    return Graphiti(
        neo4j_uri,
        neo4j_user,
        neo4j_password,
        llm_client=llm_client,
        embedder=embedder,
        cross_encoder=OpenAIRerankerClient(client=llm_client, config=llm_config),
    )


async def find_violation_nodes(graphiti: Graphiti, query: str, group_id: str):
    """通过 Graphiti 查询指定分组内名称匹配的违例节点。"""
    nodes = await graphiti.nodes.entity.get_by_group_ids([group_id])
    normalized_query = query.casefold()
    return [
        node
        for node in nodes
        if 'ViolationConcept' in node.labels and normalized_query in node.name.casefold()
    ]


async def get_phenomenon_nodes(graphiti: Graphiti, violation_uuid: str):
    """通过 Graphiti 边和节点命名空间获取违例节点的现象节点。"""
    edges = await graphiti.edges.entity.get_by_node_uuid(violation_uuid)
    phenomenon_nodes = []

    for edge in edges:
        if edge.name != 'has_phenomenon' or edge.source_node_uuid != violation_uuid:
            continue

        phenomenon = await graphiti.nodes.entity.get_by_uuid(edge.target_node_uuid)
        if 'Phenomenon' in phenomenon.labels:
            phenomenon_nodes.append(phenomenon)

    return phenomenon_nodes


async def main() -> None:
    parser = argparse.ArgumentParser(description='查询违例节点及其关联的现象节点')
    parser.add_argument('query', help='违例名称中的查询词，不区分大小写')
    parser.add_argument('--group-id', default='default', help='Graphiti group_id，默认 default')
    args = parser.parse_args()

    os.environ['SEMAPHORE_LIMIT'] = '3'
    graphiti = create_graphiti()

    try:
        violations = await find_violation_nodes(graphiti, args.query, args.group_id)
        if not violations:
            logger.info("未找到名称包含 %r 的违例节点。", args.query)
            return

        for violation in violations:
            logger.info('违例: %s', violation.name)
            phenomena = await get_phenomenon_nodes(graphiti, violation.uuid)
            if not phenomena:
                logger.info('  现象: 无')
                continue

            for phenomenon in phenomena:
                logger.info('  现象: %s', phenomenon.name)
                identification_method = phenomenon.attributes.get('identification_method')
                if identification_method:
                    logger.info('    识别方法: %s', identification_method)
    except Exception as error:
        logger.error('查询失败: %s', error, exc_info=True)
        raise
    finally:
        await graphiti.close()
        logger.info('连接已关闭')


if __name__ == '__main__':
    asyncio.run(main())
