"""
查询违例知识图谱的示例脚本
"""
import asyncio
import os
import logging
from dotenv import load_dotenv

from graphiti_core import Graphiti
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
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


async def query_examples(graphiti: Graphiti):
    """常见查询示例"""

    queries = [
        "Setup Time Violation 的根因有哪些？",
        "连线延迟过大应该怎么修复？",
        "哪些修复方法需要使用 ICC2 工具？",
        "时钟偏斜过大的排查动作是什么？",
        "如何检测 Setup Time Violation？"
    ]

    for query in queries:
        logger.info(f"\n{'='*60}")
        logger.info(f"查询: {query}")
        logger.info('='*60)

        try:
            # search() 的参数是 num_results，不是 limit
            results = await graphiti.search(query, num_results=5)

            if not results:
                logger.info("未找到相关结果")
                continue

            logger.info(f"找到 {len(results)} 条结果:\n")
            for idx, result in enumerate(results, 1):
                logger.info(f"[{idx}] {result.fact}")
                if hasattr(result, 'valid_at') and result.valid_at:
                    logger.info(f"    有效时间: {result.valid_at}")
                logger.info("")

        except Exception as e:
            logger.error(f"查询失败: {e}", exc_info=True)


async def get_node_by_name(graphiti: Graphiti, node_name: str):
    """根据名称获取节点详情"""
    logger.info(f"\n{'='*60}")
    logger.info(f"查询节点: {node_name}")
    logger.info('='*60)

    try:
        # 使用 get_by_uuid 需要先知道 uuid
        # EntityNodeNamespace 没有 get 方法，需要用其他方式查询
        # 这里改用 search 来查找节点
        results = await graphiti.search(node_name, num_results=3)

        if not results:
            logger.info(f"未找到节点: {node_name}")
            return

        logger.info(f"\n找到 {len(results)} 条相关结果:")
        for idx, edge in enumerate(results, 1):
            logger.info(f"\n[{idx}] 关系:")
            logger.info(f"  UUID: {edge.uuid}")
            logger.info(f"  事实: {edge.fact}")
            logger.info(f"  源节点: {edge.source_node_uuid}")
            logger.info(f"  目标节点: {edge.target_node_uuid}")
            if hasattr(edge, 'valid_at') and edge.valid_at:
                logger.info(f"  有效时间: {edge.valid_at}")

    except Exception as e:
        logger.error(f"查询失败: {e}", exc_info=True)


async def main():
    """主函数"""
    logger.info("初始化 Graphiti...")

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
    graphiti = Graphiti(
        neo4j_uri,
        neo4j_user,
        neo4j_password,
        llm_client=llm_client,
        embedder=embedder,
    )

    try:
        # 执行示例查询
        await query_examples(graphiti)

        # 查询特定节点
        await get_node_by_name(graphiti, "Setup Time Violation")

        logger.info("\n" + "="*60)
        logger.info("✅ 查询完成！")
        logger.info("="*60)

    except Exception as e:
        logger.error(f"❌ 发生错误: {e}", exc_info=True)
    finally:
        await graphiti.close()
        logger.info("✓ 连接已关闭")


if __name__ == '__main__':
    asyncio.run(main())
