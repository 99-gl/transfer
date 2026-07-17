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

常见的 Docker Hub mirror 候选（公共服务的可用性会随地区和时间变化，先执行上面的 manifest 测试再配置）：

```bash
MIRRORS=(
  'https://docker.1ms.run'
  'https://dockerproxy.net'
  'https://docker.m.daocloud.io'
)

for MIRROR in "${MIRRORS[@]}"; do
  echo "== ${MIRROR} =="
  curl -sS -o /dev/null \
    --connect-timeout 5 --max-time 30 \
    -H 'Accept: application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.docker.distribution.manifest.v2+json' \
    -w 'HTTP=%{http_code} total=%{time_total}s bytes=%{size_download}\n' \
    "${MIRROR}/v2/slimerl/slime/manifests/latest"
done
```

优先选择公司/学校或云厂商账户提供的专属 Docker Hub 加速地址（通常更稳定、带宽也更可控）；以上公共地址仅适合临时测试。测试返回 `HTTP=200` 且耗时稳定的源，再放到 `/etc/docker/daemon.json` 的 `registry-mirrors` 第一项。
