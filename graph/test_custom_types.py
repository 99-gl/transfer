"""
参照 Graphiti 官方文档 Custom Entity and Edge Types 的示例脚本

运行后在 Neo4j 浏览器中执行：
  MATCH (n:Entity)-[e]->(m:Entity)
  RETURN labels(n), n.name, type(e), e.name, labels(m), m.name LIMIT 20

查看 type(e) 是 RELATES_TO 还是自定义的名字
"""
import asyncio
import os
import logging
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.search.search_filters import SearchFilters

from custom_llm_client import ThinkTagCleaningClient

os.environ['GRAPHITI_TELEMETRY_ENABLED'] = 'false'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# ============================================================
# 1. 定义自定义 Entity 类型（Pydantic）
# ============================================================

class Person(BaseModel):
    """A person entity."""
    role: str | None = Field(default=None, description='Job title or role')
    age: int | None = Field(default=None, description='Age of the person')


class Organization(BaseModel):
    """An organization or company."""
    industry: str | None = Field(default=None, description='Industry the company operates in')
    headquarters: str | None = Field(default=None, description='Headquarters location')


class City(BaseModel):
    """A city."""
    country: str | None = Field(default=None, description='Country the city is in')


# ============================================================
# 2. 定义自定义 Edge 类型（Pydantic）
# ============================================================

class WorksAt(BaseModel):
    """Employment relationship between a Person and an Organization."""
    role: str | None = Field(default=None, description='Job title at the company')
    start_date: str | None = Field(default=None, description='When the person started')


class LocatedIn(BaseModel):
    """A relationship indicating something is located in a place."""


# ============================================================
# 3. edge_type_map: 哪些实体对之间允许哪些边
# ============================================================

EDGE_TYPE_MAP = {
    ('Person', 'Organization'): ['WorksAt'],
    ('Organization', 'City'): ['LocatedIn'],
    ('Person', 'City'): ['LocatedIn'],
}


async def main():
    llm_config = LLMConfig(
        api_key=os.environ.get('LOCAL_LLM_API_KEY', 'dummy-key'),
        model=os.environ.get('LOCAL_LLM_MODEL', 'qwen2.5'),
        base_url=os.environ.get('LOCAL_LLM_BASE_URL', 'http://localhost:8000/v1'),
    )
    llm_client = ThinkTagCleaningClient(
        config=llm_config,
        structured_output_mode='json_object',
    )

    embedder_config = OpenAIEmbedderConfig(
        api_key=os.environ.get('LOCAL_EMBED_API_KEY', 'dummy-key'),
        base_url=os.environ.get('LOCAL_EMBED_BASE_URL', 'http://localhost:8001/v1'),
        embedding_model='BAAI/bge-m3',
        embedding_dim=1024,
    )
    embedder = OpenAIEmbedder(config=embedder_config)

    graphiti = Graphiti(
        os.environ.get('NEO4J_URI', 'bolt://localhost:7687'),
        os.environ.get('NEO4J_USER', 'neo4j'),
        os.environ.get('NEO4J_PASSWORD', 'password'),
        llm_client=llm_client,
        embedder=embedder,
    )

    try:
        # ============================================================
        # 4. 用 add_episode 添加文本，LLM 自动提取
        # ============================================================
        episode_body = """
Alice is a software engineer at Google. She started working there in 2020.
Google is headquartered in Mountain View, which is a city in California.
Bob is a data scientist at Meta. He lives in San Francisco.
Meta is also headquartered in Menlo Park.
"""

        logger.info('=' * 60)
        logger.info('add_episode 带自定义 entity_types / edge_types / edge_type_map')
        logger.info('=' * 60)
        logger.info(f'entity_types: Person, Organization, City')
        logger.info(f'edge_types: WorksAt, LocatedIn')
        logger.info(f'edge_type_map: {EDGE_TYPE_MAP}')
        logger.info('')

        result = await graphiti.add_episode(
            name='test_custom_types',
            episode_body=episode_body,
            source=EpisodeType.text,
            source_description='官方文档自定义类型测试',
            reference_time=datetime.now(timezone.utc),

            entity_types={
                'Person': Person,
                'Organization': Organization,
                'City': City,
            },
            edge_types={
                'WorksAt': WorksAt,
                'LocatedIn': LocatedIn,
            },
            edge_type_map=EDGE_TYPE_MAP,
        )

        # ============================================================
        # 5. 查看提取结果
        # ============================================================
        logger.info('=' * 60)
        logger.info('提取结果')
        logger.info('=' * 60)

        logger.info(f'\n节点 ({len(result.nodes)} 个):')
        for node in result.nodes:
            logger.info(f'  - labels={node.labels}  name={node.name}')
            if node.attributes:
                for k, v in node.attributes.items():
                    logger.info(f'      {k}: {v}')

        logger.info(f'\n边 ({len(result.edges)} 个):')
        for edge in result.edges:
            logger.info(f'  - name="{edge.name}"')
            logger.info(f'    fact: {edge.fact}')

        # ============================================================
        # 6. 搜索测试
        # ============================================================
        logger.info(f'\n{"=" * 60}')
        logger.info('搜索测试')
        logger.info('=' * 60)

        results = await graphiti.search('Who works at Google?', num_results=5)
        logger.info(f'\n搜索 "Who works at Google?": {len(results)} 条')
        for r in results:
            logger.info(f'  name="{r.name}" | {r.fact}')

        # 按边类型过滤
        logger.info(f'\n按 edge_names=["WorksAt"] 过滤:')
        results_w = await graphiti.search(
            'Where do people work?',
            num_results=5,
            search_filter=SearchFilters(edge_names=['WorksAt']),
        )
        for r in results_w:
            logger.info(f'  name="{r.name}" | {r.fact}')

        # ============================================================
        # 7. 验证 Neo4j
        # ============================================================
        logger.info(f'\n{"=" * 60}')
        logger.info('请在 Neo4j 浏览器中执行以下 Cypher 验证:')
        logger.info('=' * 60)
        logger.info('')
        logger.info('  MATCH (n:Entity)-[e]->(m:Entity)')
        logger.info('  RETURN labels(n), n.name, type(e) AS arrow_type,')
        logger.info('         e.name AS edge_name, labels(m), m.name')
        logger.info('  LIMIT 20')
        logger.info('')
        logger.info(' 若 arrow_type 全是 RELATES_TO → 边类型写死在代码里')
        logger.info(' 若 arrow_type 是 WorksAt/LocatedIn → edge_type_map 真改了箭头')
        logger.info('')

    finally:
        await graphiti.close()
        logger.info('Done.')


if __name__ == '__main__':
    asyncio.run(main())
