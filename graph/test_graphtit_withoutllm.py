import asyncio
from neo4j import AsyncGraphDatabase

async def test_neo4j_connection():
    """测试 Neo4j 连接，不涉及 LLM"""
    uri = "bolt://localhost:7687"  # 如果改了端口记得改这里
    user = "neo4j"
    password = "your_password"  # 改成你设置的密码
    
    print("Testing Neo4j connection...")
    
    try:
        driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        
        async with driver.session() as session:
            # 简单查询测试
            result = await session.run("RETURN 1 AS num")
            record = await result.single()
            print(f"✅ Connection successful! Test query returned: {record['num']}")
            
            # 查看数据库版本
            result = await session.run("CALL dbms.components() YIELD name, versions")
            async for record in result:
                print(f"📦 {record['name']}: {record['versions'][0]}")
        
        await driver.close()
        print("✅ Neo4j connection test passed!")
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_neo4j_connection())
