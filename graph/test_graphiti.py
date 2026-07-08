import asyncio
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType

async def main():
    # 初始化 Graphiti
    graphiti = Graphiti(
        neo4j_uri="bolt://localhost:7687",  # 如果改了端口记得改这里
        neo4j_user="neo4j",
        neo4j_password="your_password"  # 改成你设置的密码
    )
    
    print("Adding episode...")
    await graphiti.add_episode(
        name="test_episode",
        episode_body="Alice met Bob at the park. They discussed machine learning.",
        episode_type=EpisodeType.text,
        source_description="Test conversation"
    )
    
    print("Searching...")
    results = await graphiti.search("Alice")
    print(f"Found {len(results)} results:")
    for r in results:
        print(r)
    
    await graphiti.close()

if __name__ == "__main__":
    asyncio.run(main())
