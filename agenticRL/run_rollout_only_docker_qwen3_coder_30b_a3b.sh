#!/usr/bin/env bash
# One-node, inference-only Claude Code rollout using Qwen3-Coder-30B-A3B-Instruct.
# It starts SGLang through Slime, then runs exactly one Docker-backed SWE task.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SLIME_DIR="${SLIME_DIR:-${REPO_ROOT}/slime}"

: "${HF_CHECKPOINT:?Set HF_CHECKPOINT to the Qwen3-Coder-30B-A3B-Instruct HF directory}"
: "${PROMPT_DATA:?Set PROMPT_DATA to a JSONL task file; see sample_task.jsonl}"
: "${SLIME_AGENT_NODE_TARBALL:?Set path to node-v22.*-linux-x64.tar.xz}"
: "${SLIME_AGENT_CC_TARBALL:?Set path to anthropic-ai-claude-code-local-linux-x64.tgz}"

# Choose values that fit the actual GPUs.  TP must divide ROLLOUT_NUM_GPUS.
ROLLOUT_NUM_GPUS="${ROLLOUT_NUM_GPUS:-4}"
ROLLOUT_TP_SIZE="${ROLLOUT_TP_SIZE:-4}"
ROLLOUT_MEM_FRACTION="${ROLLOUT_MEM_FRACTION:-0.85}"
RUN_ROOT="${RUN_ROOT:-${REPO_ROOT}/transfer/agenticRL/runs/$(date +%Y%m%d_%H%M%S)}"

if (( ROLLOUT_NUM_GPUS % ROLLOUT_TP_SIZE != 0 )); then
  echo "ROLLOUT_NUM_GPUS must be divisible by ROLLOUT_TP_SIZE" >&2
  exit 2
fi

mkdir -p "${RUN_ROOT}/rollout_dumps"
export PYTHONPATH="${REPO_ROOT}:${SLIME_DIR}:${PYTHONPATH:-}"

# Each Docker task container calls back to its local Ray worker's adapter.
# DockerSandbox adds host.docker.internal -> host-gateway when it starts it.
export ADAPTER_PUBLIC_HOST="${ADAPTER_PUBLIC_HOST:-host.docker.internal}"
export ADAPTER_BIND_HOST="${ADAPTER_BIND_HOST:-0.0.0.0}"
export ADAPTER_PORT="${ADAPTER_PORT:-18001}"
export SLIME_AGENT_DOCKER_NETWORK="${SLIME_AGENT_DOCKER_NETWORK:-bridge}"
export SWE_AGENT="claude_code"
export SWE_AGENT_TIME_BUDGET_SEC="${SWE_AGENT_TIME_BUDGET_SEC:-300}"
export SWE_EVAL_TIMEOUT_SEC="${SWE_EVAL_TIMEOUT_SEC:-300}"
export SWE_BOOT_CONCURRENCY="${SWE_BOOT_CONCURRENCY:-1}"
export no_proxy="${no_proxy:-127.0.0.1,localhost,host.docker.internal}"
export NO_PROXY="${NO_PROXY:-${no_proxy}}"

# A rollout-only process does not create Megatron workers. Ray only reserves
# ROLLOUT_NUM_GPUS for SGLang. Start this in a clean, single-node Ray session.
ray start --head --num-gpus "${ROLLOUT_NUM_GPUS}" --disable-usage-stats

cd "${SLIME_DIR}"
python3 -u train.py \
  --debug-rollout-only \
  --actor-num-nodes 1 \
  --actor-num-gpus-per-node "${ROLLOUT_NUM_GPUS}" \
  --hf-checkpoint "${HF_CHECKPOINT}" \
  --custom-generate-function-path transfer.agenticRL.docker_generate.generate \
  --prompt-data "${PROMPT_DATA}" \
  --input-key prompt \
  --label-key label \
  --metadata-key metadata \
  --num-rollout 1 \
  --rollout-batch-size 1 \
  --n-samples-per-prompt 1 \
  --rollout-num-gpus "${ROLLOUT_NUM_GPUS}" \
  --rollout-num-gpus-per-engine "${ROLLOUT_TP_SIZE}" \
  --rollout-max-context-len 32768 \
  --rollout-max-response-len 8192 \
  --rollout-temperature 0.2 \
  --sglang-mem-fraction-static "${ROLLOUT_MEM_FRACTION}" \
  --sglang-tool-call-parser qwen3_coder \
  --sglang-reasoning-parser qwen3 \
  --save-debug-rollout-data "${RUN_ROOT}/rollout_dumps/rollout_{rollout_id}.pt" \
  2>&1 | tee "${RUN_ROOT}/run.log"
