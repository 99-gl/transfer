# Agent Adapter Service

一个独立的 HTTP 服务：接收 OpenAI Chat Completions 或 Anthropic Messages 请求，将请求转换为同一份 tokenizer chat template 输入，调用 SGLang `/generate`，并把每个完成的交互回合写入按轨迹分组的 JSONL 文件。

它是一个**协议适配与原始轨迹采集器**，不是训练框架：不包含 reward、loss mask、跨轮 token 对齐、训练样本组装、Ray、Megatron、sandbox 或 agent CLI 生命周期。

## 数据流

```text
OpenAI / Anthropic 客户端
          │ HTTP 请求
          ▼
协议规范化（protocols.py） ──► NormalizedRequest
          │ messages + tools + sampling params + trajectory_id
          ▼
Tokenizer chat template（server.py） ──► prompt_token_ids
          ▼
SGLangClient（sglang.py） ──► output_token_ids + logprobs
          ▼
输出解析（parsing.py） ──► text + XML tool calls
          ├──────────────────────────► JsonlRecorder（recording.py）
          │                              `trajectories/<id>.jsonl`
          ▼
原协议响应（protocols.py） ──► OpenAI / Anthropic 客户端
```

## 模块职责

| 模块 | 输入 | 输出 | 职责 |
| --- | --- | --- | --- |
| `protocols.py` | HTTP request + JSON body | `NormalizedRequest` / 客户端响应 | OpenAI、Anthropic 协议的解析、标准化及响应渲染 |
| `models.py` | — | 数据类 | 模块间稳定的数据契约：请求、生成结果、解析结果 |
| `server.py` | `NormalizedRequest` | HTTP response | 编排主流程；调用 tokenizer、SGLang、解析器和记录器 |
| `sglang.py` | token IDs、采样参数、路由键 | `Generation` | 唯一负责 SGLang HTTP 调用及取消时的 abort |
| `parsing.py` | 解码后的模型文本、工具 schema、parser 配置 | `ParsedOutput` | 用 SGLang parser 分离 reasoning/tool calls；XML tool call 是未配置 parser 时的 fallback |
| `recording.py` | `trajectory_id`、一轮记录 | JSONL 文件 | 每条轨迹单独追加、加 `turn_index`、服务重启后继续计数 |
| `serve.py` | CLI 参数 | aiohttp 服务 | 加载 tokenizer 并启动服务 |

## 输入

### OpenAI

- Endpoint: `POST /v1/chat/completions`
- 轨迹身份优先级：`Authorization: Bearer <token>` → `metadata.session_id` → `user` → `default`
- 支持 `messages`、function `tools`、`max_tokens` / `max_completion_tokens` / `max_output_tokens`、`temperature`、`top_p`、`top_k`、`stop` 与 `stream`。

### Anthropic

- Endpoint: `POST /v1/messages`
- 轨迹身份优先级：`Authorization: Bearer <token>` → `X-Api-Key` → `default`
- Claude Code 通常通过 `ANTHROPIC_AUTH_TOKEN` 设置 token；同一个 token 即同一条轨迹。
- 支持 `system`、`messages`、Anthropic tool schema、`max_tokens`、`temperature`、`top_p`、`top_k`、`stop_sequences` 与 `stream`。
- `POST /v1/messages/count_tokens` 返回 `0`，仅用于兼容将它作为提示信息的客户端，不进行精确计数。

身份值只在内存中用于计算 `trajectory_id`，不会写入 JSONL 或文件名。`trajectory_id = sha256(identity)`；因此必须给每个并发 agent/rollout 一个唯一 token，否则它们会被记录到同一条轨迹。

## 模型输出解析

调用方向是：**agent → adapter → SGLang 模型 → adapter → agent**。adapter 调用的是低层 SGLang `/generate`，它获得的是生成 token ID 及其解码文本；adapter 必须把该文本解析为 reasoning、可见文本和 tool call，才可以封装为 Anthropic/OpenAI 所需的响应对象。

因此，若模型部署时使用了 SGLang 的 `--tool-call-parser` 或 `--reasoning-parser`，启动 adapter 时也要传入**同一个模型对应的同名配置**：

```bash
uv run python serve.py \
  --model /models/MODEL \
  --sglang-url http://127.0.0.1:30000 \
  --output-dir ./data \
  --tool-call-parser <MODEL_TOOL_CALL_PARSER> \
  --reasoning-parser <MODEL_REASONING_PARSER>
```

`MODEL_TOOL_CALL_PARSER` 与 `MODEL_REASONING_PARSER` 都是 `/models/MODEL` 的配置，不代表两类模型：前者描述这个模型的工具调用格式，后者描述这个模型的 reasoning 格式。两者都必须与启动同一台 SGLang server 时使用的 `--tool-call-parser` 和 `--reasoning-parser` 完全一致。

若未传 `--tool-call-parser`，adapter 会尝试 Anthropic 风格 XML tool call 作为有限 fallback；其他模型私有格式不会猜测解析，以免把普通文本误当工具调用。若配置 parser 但本地环境没有 `sglang` Python 包，adapter 会明确报错，而不会悄悄返回错误格式。

`requirements.txt` 包含 `sglang`，因为 parser 在 adapter 进程内执行，而不仅在远端 server 上执行。

## 输出

HTTP 响应保持输入协议：OpenAI 请求得到 Chat Completions 格式，Anthropic 请求得到 Messages 格式。服务先等待 SGLang 完成一轮生成，再返回结果；当 `stream=true` 时输出兼容的 SSE 包装，**不是逐 token 的实时转发**。

`--output-dir` 下的结构如下：

```text
data/
  trajectories/
    84097828fc31...cb7a98b.jsonl  # 一条 trajectory
```

一个 JSONL 文件是一条完整的多轮轨迹；其中**每一行是一轮交互**。同一客户端通常会在每轮请求中重复携带历史 `messages`，所以 `request` 是该轮的完整请求快照，不应把每行的历史重复拼接。

示例（格式化后展示，文件中实际为单行）：

```json
{
  "schema_version": 1,
  "turn_index": 2,
  "recorded_at": 1785740123.45,
  "protocol": "anthropic",
  "trajectory_id": "84097828fc31a8c8d29210df48901a85de7fd013f686b17be77d1be29cb7a98b",
  "model": "adapter-model",
  "request_id": "a3d9f2...",
  "request": {"model": "adapter-model", "messages": [{"role": "user", "content": "继续"}]},
  "normalized_messages": [{"role": "user", "content": "继续"}],
  "tools": null,
  "parser_config": {"tool_call_parser": "<MODEL_TOOL_CALL_PARSER>", "reasoning_parser": "<MODEL_REASONING_PARSER>"},
  "sampling_params": {"max_new_tokens": 256, "temperature": 0.7},
  "prompt_token_ids": [151644, 872, 198],
  "output_token_ids": [77091, 198],
  "output_logprobs": [-0.12, -0.36],
  "raw_output": "好的。",
  "parsed_output": {"reasoning": "", "text": "好的。", "tool_uses": []},
  "finish_reason": "stop"
}
```

JSONL 会存储 prompt、tool result 和模型输出，按敏感数据处理。`trajectory_id` 虽非明文 token，仍是稳定关联标识；如 token 熵较低，仍可能被离线猜测。

## 运行

```bash
cd agent_adapter_service
uv sync

uv run python serve.py \
  --model /models/MODEL \
  --sglang-url http://127.0.0.1:30000 \
  --output-dir ./data \
  --host 0.0.0.0 \
  --port 18001 \
  --tool-call-parser <MODEL_TOOL_CALL_PARSER> \
  --reasoning-parser <MODEL_REASONING_PARSER> \
  --trust-remote-code
```

将两个 placeholder 替换为同一 `MODEL` 在 SGLang 部署中实际使用的 parser 名称。

- OpenAI-compatible client base URL: `http://HOST:18001/v1`
- Anthropic-compatible client base URL: `http://HOST:18001`

## 验证

```bash
uv run python -m unittest discover -s tests -v
```

`requirements.txt` 仅保留给不使用 uv 的兼容场景；标准安装入口是 `pyproject.toml` + `uv sync`。首次使用需要先安装 uv（见 <https://docs.astral.sh/uv/getting-started/installation/>）。
