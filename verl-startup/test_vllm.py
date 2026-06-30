from openai import OpenAI

client = OpenAI(
    api_key="EMPTY",
    base_url="http://127.0.0.1:8000/v1",
)

resp = client.chat.completions.create(
    model="qwen3-4b",  # 或者写你的本地模型路径
    messages=[
        {"role": "user", "content": "你好，介绍一下你自己"}
    ],
    max_tokens=256,
    temperature=0.7,
)

print(resp.choices[0].message.content)