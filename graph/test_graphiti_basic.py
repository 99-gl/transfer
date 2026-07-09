import asyncio
import json
import os
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.embedder import OpenAIEmbedder

# 导入自定义的清理 think 标签的 Client
from custom_llm_client import ThinkTagCleaningClient

# 禁用遥测
os.environ['GRAPHITI_TELEMETRY_ENABLED'] = 'false'

# 启用详细日志以查看模型实际返回内容
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 加载 .env 文件
load_dotenv()

# 从环境变量读取配置
neo4j_uri = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
neo4j_user = os.environ.get('NEO4J_USER', 'neo4j')
neo4j_password = os.environ.get('NEO4J_PASSWORD', 'password')

# 本地 LLM 配置
local_llm_base_url = os.environ.get('LOCAL_LLM_BASE_URL', 'http://localhost:8000/v1')
local_llm_model = os.environ.get('LOCAL_LLM_MODEL', 'qwen2.5')  # 改成你的 LLM 模型名
local_llm_api_key = os.environ.get('LOCAL_LLM_API_KEY', 'dummy-key')

# 本地 Embedding 配置
local_embed_base_url = os.environ.get('LOCAL_EMBED_BASE_URL', 'http://localhost:8001/v1')
local_embed_api_key = os.environ.get('LOCAL_EMBED_API_KEY', 'dummy-key')

if not neo4j_uri or not neo4j_user or not neo4j_password:
    raise ValueError('NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD must be set in .env')


async def main():
    print("Initializing Graphiti with local LLM and Embedding...")
    print("⚙️  Telemetry disabled")
    print("⚙️  Logging level: DEBUG")
    print("⚙️  Structured output mode: json_object")
    print("⚙️  Lower concurrency to avoid rate limits")

    # 降低并发限制，避免本地模型过载或速率限制
    os.environ['SEMAPHORE_LIMIT'] = '3'

    # 配置本地 LLM（用于实体抽取、关系推理等）
    llm_config = LLMConfig(
        api_key=local_llm_api_key,
        model=local_llm_model,
        base_url=local_llm_base_url,
    )

    # 使用自定义的 ThinkTagCleaningClient 自动清理 <think> 标签
    llm_client = ThinkTagCleaningClient(
        config=llm_config,
        structured_output_mode="json_object"  # 使用 json_object 而非 json_schema，兼容性更好
    )

    # 配置本地 Embedding（用于向量检索）
    embedder_config = LLMConfig(
        api_key=local_embed_api_key,
        base_url=local_embed_base_url,
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
