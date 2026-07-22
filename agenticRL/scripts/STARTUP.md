# Claude Code + Slime Adapter + SGLang 启动命令

以下示例让 Claude Code 通过 Slime 的 Anthropic Adapter 调用本地 SGLang
中的 `Qwen3-Coder-30B-A3B`。请先按实际情况修改宿主机模型和代码目录。

```bash
export MODEL_DIR=/data/slime/models/Qwen3-Coder-30B-A3B
export WORKSPACE_DIR=/data/agent-workspace
export SCRIPT_DIR=/data/slime/adapter
export TRAJECTORY_DIR=/data/slime/trajectory
```

三个容器必须位于同一个 Docker 网络。首次执行时创建网络：

```bash
docker network create agent-net
```

## 1. 启动 SGLang

此示例让容器可见全部 GPU，但 SGLang 仅使用宿主机的第 4、5 张 GPU。

```bash
docker run -d --name sglang \
  --network agent-net \
  --gpus all \
  -e CUDA_VISIBLE_DEVICES=4,5 \
  -v "${MODEL_DIR}:/model:ro" \
  -p 30000:30000 \
  slimerl/slime:latest \
  python3 -m sglang.launch_server \
    --model-path /model \
    --tp 2 \
    --tool-call-parser qwen3_coder \
    --reasoning-parser qwen3 \
    --host 0.0.0.0 \
    --port 30000
```

等待服务就绪：

```bash
docker logs -f sglang
```

## 2. 启动 Slime Anthropic Adapter

将本目录中的 `serve_anthropic_adapter.py` 放在宿主机的 `${SCRIPT_DIR}`
（或将 `SCRIPT_DIR` 改为其实际所在目录）。Adapter 会监听 18001 端口，
并将 Anthropic Messages 请求转发到同网络中的 `sglang:30000`。

```bash
docker run -d --name slime-anthropic-adapter \
  --network agent-net \
  -p 18001:18001 \
  -e MODEL_PATH=/model \
  -e SGLANG_URL=http://sglang:30000 \
  -e SGLANG_TOOL_CALL_PARSER=qwen3_coder \
  -e SGLANG_REASONING_PARSER=qwen3 \
  -e TRAJECTORY_LOG_PATH=/logs/trajectory.jsonl \
  -v "${MODEL_DIR}:/model:ro" \
  -v "${SCRIPT_DIR}:/app:ro" \
  -v "${TRAJECTORY_DIR}:/logs" \
  slimerl/slime:latest \
  python3 /app/serve_anthropic_adapter.py
```

检查 Adapter：

```bash
curl http://127.0.0.1:18001/healthz
```

每个完成的 Claude Code 回合会追加到宿主机：

```bash
tail -f "${TRAJECTORY_DIR}/trajectory.jsonl"
```

## 3. 启动 Claude Code sandbox

将 `你的-claude-code-sandbox镜像` 替换为已经安装 Node 与 Claude Code CLI 的
自建镜像。`ANTHROPIC_BASE_URL` 指向 **Adapter**，不要填 SGLang 的 30000 端口，
也不要加 `/v1`。

```bash
docker run --rm -it \
  --network agent-net \
  -e ANTHROPIC_BASE_URL=http://slime-anthropic-adapter:18001 \
  -e ANTHROPIC_AUTH_TOKEN=claude-test-session-001 \
  -e ANTHROPIC_MODEL=Qwen3-Coder-30B-A3B \
  -v "${WORKSPACE_DIR}:/workspace" \
  你的-claude-code-sandbox镜像 \
  bash
```

进入 sandbox 后运行：

```bash
cd /workspace
claude -p "请阅读项目结构，修复测试失败的问题，并运行相关测试。" \
  --permission-mode bypassPermissions
```

## 停止

```bash
docker rm -f slime-anthropic-adapter sglang
```

删除容器不会删除宿主机中的模型或工作目录。
