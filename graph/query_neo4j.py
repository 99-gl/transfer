"""
查询 Neo4j 图数据库中的节点和关系
可以在服务器上直接运行，无需浏览器
"""
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

# 配置
neo4j_uri = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
neo4j_user = os.environ.get('NEO4J_USER', 'neo4j')
neo4j_password = os.environ.get('NEO4J_PASSWORD', 'password')


def query_all_nodes(driver, limit=20):
    """查询所有节点"""
    print(f"\n{'='*60}")
    print(f"所有节点 (限制 {limit} 条)")
    print(f"{'='*60}")

    with driver.session() as session:
        result = session.run(f"MATCH (n) RETURN n LIMIT {limit}")
        count = 0
        for record in result:
            count += 1
            node = record['n']
            labels = list(node.labels)
            props = dict(node.items())
            print(f"\n节点 {count}:")
            print(f"  标签: {labels}")
            print(f"  属性: {props}")

    if count == 0:
        print("  (无节点)")


def query_node_statistics(driver):
    """统计各类型节点数量"""
    print(f"\n{'='*60}")
    print("节点统计")
    print(f"{'='*60}")

    with driver.session() as session:
        result = session.run("""
            MATCH (n)
            RETURN labels(n) as NodeType, count(n) as Count
            ORDER BY Count DESC
        """)

        total = 0
        for record in result:
            node_type = record['NodeType']
            count = record['Count']
            total += count
            print(f"  {node_type}: {count} 个")

        print(f"\n  总计: {total} 个节点")


def query_relationships(driver, limit=20):
    """查询所有关系"""
    print(f"\n{'='*60}")
    print(f"所有关系 (限制 {limit} 条)")
    print(f"{'='*60}")

    with driver.session() as session:
        result = session.run(f"""
            MATCH (n)-[r]->(m)
            RETURN n, r, m
            LIMIT {limit}
        """)

        count = 0
        for record in result:
            count += 1
            source = record['n']
            rel = record['r']
            target = record['m']

            source_name = dict(source.items()).get('name', 'N/A')
            target_name = dict(target.items()).get('name', 'N/A')
            rel_type = type(rel).__name__

            print(f"\n关系 {count}:")
            print(f"  {source_name} --[{rel_type}]--> {target_name}")
            print(f"  关系属性: {dict(rel.items())}")

        if count == 0:
            print("  (无关系)")


def query_entities(driver, limit=20):
    """查询实体节点"""
    print(f"\n{'='*60}")
    print(f"实体节点 (限制 {limit} 条)")
    print(f"{'='*60}")

    with driver.session() as session:
        result = session.run(f"""
            MATCH (n:Entity)
            RETURN n
            LIMIT {limit}
        """)

        count = 0
        for record in result:
            count += 1
            node = record['n']
            props = dict(node.items())

            print(f"\n实体 {count}:")
            print(f"  名称: {props.get('name', 'N/A')}")
            print(f"  摘要: {props.get('summary', 'N/A')}")
            print(f"  UUID: {props.get('uuid', 'N/A')}")

        if count == 0:
            print("  (无实体节点)")


def query_episodes(driver, limit=10):
    """查询 Episode 节点"""
    print(f"\n{'='*60}")
    print(f"Episode 节点 (限制 {limit} 条)")
    print(f"{'='*60}")

    with driver.session() as session:
        result = session.run(f"""
            MATCH (e:Episode)
            RETURN e
            LIMIT {limit}
        """)

        count = 0
        for record in result:
            count += 1
            node = record['e']
            props = dict(node.items())

            print(f"\nEpisode {count}:")
            print(f"  名称: {props.get('name', 'N/A')}")
            print(f"  内容: {props.get('content', 'N/A')[:100]}...")  # 只显示前100字符
            print(f"  创建时间: {props.get('created_at', 'N/A')}")

        if count == 0:
            print("  (无 Episode 节点)")


def search_by_name(driver, name):
    """根据名称搜索节点"""
    print(f"\n{'='*60}")
    print(f"搜索包含 '{name}' 的节点")
    print(f"{'='*60}")

    with driver.session() as session:
        result = session.run("""
            MATCH (n)
            WHERE n.name CONTAINS $name
            RETURN n
        """, name=name)

        count = 0
        for record in result:
            count += 1
            node = record['n']
            labels = list(node.labels)
            props = dict(node.items())

            print(f"\n节点 {count}:")
            print(f"  标签: {labels}")
            print(f"  名称: {props.get('name', 'N/A')}")
            print(f"  摘要: {props.get('summary', 'N/A')}")

        if count == 0:
            print(f"  未找到包含 '{name}' 的节点")


def main():
    print("连接到 Neo4j...")
    print(f"URI: {neo4j_uri}")
    print(f"用户: {neo4j_user}")

    driver = GraphDatabase.driver(
        neo4j_uri,
        auth=(neo4j_user, neo4j_password)
    )

    try:
        # 测试连接
        with driver.session() as session:
            session.run("RETURN 1")
        print("✅ 连接成功!\n")

        # 执行各种查询
        query_node_statistics(driver)
        query_entities(driver, limit=10)
        query_episodes(driver, limit=5)
        query_relationships(driver, limit=10)

        # 搜索特定内容（示例）
        search_by_name(driver, "Alice")

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

    finally:
        driver.close()
        print("\n✅ 连接已关闭")


if __name__ == "__main__":
    main()
