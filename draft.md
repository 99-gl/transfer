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
```bash
curl -sS -o /dev/null \
  --connect-timeout 5 --max-time 30 \
  -H 'Accept: application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.docker.distribution.manifest.v2+json' \
  -w 'HTTP=%{http_code} total=%{time_total}s bytes=%{size_download}\n' \
  "${MIRROR}/v2/slimerl/slime/manifests/latest"
```
