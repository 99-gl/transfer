import asyncio
import json
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from graphiti_core.llm_client import OpenAIClient
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.embedder import OpenAIEmbedder

# 加载 .env 文件
load_dotenv()

# 从环境变量读取配置
neo4j_uri = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
neo4j_user = os.environ.get('NEO4J_USER', 'neo4j')
neo4j_password = os.environ.get('NEO4J_PASSWORD', 'password')

# 本地 LLM 配置
local_llm_base_url = os.environ.get('LOCAL_LLM_BASE_URL', 'http://localhost:8000/v1')
local_llm_model = os.environ.get('LOCAL_LLM_MODEL', 'gpt-3.5-turbo')  # 改成你的模型名
local_llm_api_key = os.environ.get('LOCAL_LLM_API_KEY', 'dummy-key')  # 本地可能不需要真实 key

if not neo4j_uri or not neo4j_user or not neo4j_password:
    raise ValueError('NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD must be set in .env')


async def main():
    print("Initializing Graphiti with local LLM...")

    # 配置本地 LLM
    llm_config = LLMConfig(
        api_key=local_llm_api_key,
        model=local_llm_model,
        base_url=local_llm_base_url,
    )
    llm_client = OpenAIClient(config=llm_config)

    # 配置本地 Embedder（如果你的 embedding 也是本地的）
    embedder_config = LLMConfig(
        api_key=local_llm_api_key,
        base_url=local_llm_base_url,
    )
    embedder = OpenAIEmbedder(config=embedder_config)

    # 初始化 Graphiti，传入自定义的 llm_client 和 embedder
    graphiti = Graphiti(
        neo4j_uri,
        neo4j_user,
        neo4j_password,
        llm_client=llm_client,
        embedder=embedder,
    )

    try:
        print("✅ Graphiti initialized successfully!")

        # 添加一个简单的 episode
        print("\nAdding episode...")
        await graphiti.add_episode(
            name='test_episode_1',
            episode_body='Alice is a data scientist. She works at OpenAI.',
            source=EpisodeType.text,
            source_description='test conversation',
            reference_time=datetime.now(timezone.utc),
        )
        print("✅ Episode added successfully!")

        # 搜索
        print("\nSearching for 'Alice'...")
        results = await graphiti.search('Who is Alice?')

        print(f"\nFound {len(results)} results:")
        for result in results:
            print(f"  - Fact: {result.fact}")
            print(f"    UUID: {result.uuid}")
            print("---")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await graphiti.close()
        print("\n✅ Connection closed")


if __name__ == '__main__':
    asyncio.run(main())
