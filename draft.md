curl -X POST "http://localhost:8000/tokenize" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-7B",
    "messages": [
      {"role": "user", "content": "What is the capital of France?"}
    ],
    "return_token_strs": true,
    "extra_body": {
      "chat_template_kwargs": {
        "enable_thinking": true
      }
    }
  }'