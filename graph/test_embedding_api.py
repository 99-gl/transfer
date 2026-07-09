"""
测试 vLLM Embedding API 是否正常工作
"""
import requests
import json

# 配置
EMBEDDING_URL = "http://localhost:8001/v1/embeddings"
MODEL_NAME = "BAAI/bge-m3"
TEST_INPUT = "Hello world"

def test_embedding_api():
    """测试 embedding API"""
    print(f"Testing Embedding API at: {EMBEDDING_URL}")
    print(f"Model: {MODEL_NAME}")
    print(f"Input: {TEST_INPUT}")
    print("-" * 50)

    # 构造请求
    payload = {
        "model": MODEL_NAME,
        "input": TEST_INPUT
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        # 发送请求
        response = requests.post(
            EMBEDDING_URL,
            headers=headers,
            data=json.dumps(payload),
            timeout=30
        )

        # 检查状态码
        if response.status_code == 200:
            print("✅ API 请求成功!")

            # 解析响应
            result = response.json()

            # 显示基本信息
            print(f"\n响应信息:")
            print(f"  - Model: {result.get('model', 'N/A')}")
            print(f"  - Object: {result.get('object', 'N/A')}")

            # 显示 embedding 信息
            if 'data' in result and len(result['data']) > 0:
                embedding = result['data'][0].get('embedding', [])
                print(f"  - Embedding dimension: {len(embedding)}")
                print(f"  - First 10 values: {embedding[:10]}")
                print(f"\n✅ Embedding 模型工作正常!")
            else:
                print("⚠️  响应中没有 embedding 数据")
                print(f"完整响应: {json.dumps(result, indent=2)}")

        else:
            print(f"❌ API 请求失败!")
            print(f"状态码: {response.status_code}")
            print(f"响应内容: {response.text}")

    except requests.exceptions.ConnectionError:
        print("❌ 连接失败!")
        print("请确保 vLLM Embedding 服务已启动:")
        print("  bash start_embedding_vllm.sh")
        print(f"\n或检查服务是否在 {EMBEDDING_URL} 运行")

    except requests.exceptions.Timeout:
        print("❌ 请求超时!")
        print("服务可能正在加载模型，请稍后再试")

    except Exception as e:
        print(f"❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_embedding_api()
