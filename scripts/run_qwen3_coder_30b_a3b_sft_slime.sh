#!/usr/bin/env bash
#
# Usage (Linux shell, single 8x A100 80GB node):
#   # Run inside the official Slime image. Mount /data from the host first.
#   export MODEL_DIR=/data/models/Qwen3-Coder-30B-A3B-Instruct
#   export REF_LOAD=/data/checkpoints/Qwen3-Coder-30B-A3B_torch_dist
#   export LOAD=/data/checkpoints/Qwen3-Coder-30B-A3B_sft_init
#   export SAVE=/data/checkpoints/Qwen3-Coder-30B-A3B_swesmith_sft
#   export TRAIN_DATA=/data/swesmith_claude_code.jsonl
#   bash /data/sweTrain/scripts/run_qwen3_coder_30b_a3b_sft_slime.sh
#
# The official image provides Slime at /root/slime and Megatron-LM at
# /root/Megatron-LM. REF_LOAD and LOAD must already be checkpoints converted
# from MODEL_DIR with Slime's model-conversion workflow.
#
# This launch configuration is for one machine with 8 GPUs.  For a multi-node
# run, start Ray workers yourself and set ACTOR_NUM_NODES accordingly.

set -euo pipefail

SLIME_DIR="/root/slime"
MEGATRON_DIR="/root/Megatron-LM"
: "${MODEL_DIR:?Set MODEL_DIR to Qwen3-Coder-30B-A3B-Instruct.}"
: "${REF_LOAD:?Set REF_LOAD to the converted immutable reference checkpoint.}"
: "${LOAD:?Set LOAD to an initial converted training checkpoint.}"
: "${SAVE:?Set SAVE to the output checkpoint directory.}"
: "${TRAIN_DATA:?Set TRAIN_DATA to the converted JSONL dataset.}"

GPUS_PER_NODE="${GPUS_PER_NODE:-8}"
ACTOR_NUM_NODES="${ACTOR_NUM_NODES:-1}"
MASTER_ADDR="${MASTER_ADDR:-127.0.0.1}"
MAX_SEQUENCE_LENGTH="${MAX_SEQUENCE_LENGTH:-32768}"
MAX_TOKENS_PER_GPU="${MAX_TOKENS_PER_GPU:-16384}"
CONTEXT_PARALLEL_SIZE="${CONTEXT_PARALLEL_SIZE:-2}"
ROLLOUT_BATCH_SIZE="${ROLLOUT_BATCH_SIZE:-8}"
GLOBAL_BATCH_SIZE="${GLOBAL_BATCH_SIZE:-16}"
NUM_EPOCHS="${NUM_EPOCHS:-1}"
LEARNING_RATE="${LEARNING_RATE:-5e-6}"
SAVE_INTERVAL="${SAVE_INTERVAL:-200}"
START_RAY="${START_RAY:-1}"

for path in "$SLIME_DIR" "$MEGATRON_DIR" "$MODEL_DIR" "$REF_LOAD" "$LOAD" "$TRAIN_DATA"; do
    [[ -e "$path" ]] || { echo "Required path does not exist: $path" >&2; exit 2; }
done
[[ "$((CONTEXT_PARALLEL_SIZE * MAX_TOKENS_PER_GPU))" -ge "$MAX_SEQUENCE_LENGTH" ]] || {
    echo "CONTEXT_PARALLEL_SIZE * MAX_TOKENS_PER_GPU must cover MAX_SEQUENCE_LENGTH." >&2
    exit 2
}
[[ "$((MAX_SEQUENCE_LENGTH % CONTEXT_PARALLEL_SIZE))" -eq 0 ]] || {
    echo "MAX_SEQUENCE_LENGTH must be divisible by CONTEXT_PARALLEL_SIZE." >&2
    exit 2
}

export PYTHONUNBUFFERED=1
export PYTHONPATH="${SLIME_DIR}:${MEGATRON_DIR}${PYTHONPATH:+:${PYTHONPATH}}"
export no_proxy="127.0.0.1,${MASTER_ADDR}"

if [[ "$START_RAY" == "1" ]]; then
    ray start --head --node-ip-address "$MASTER_ADDR" --num-gpus "$GPUS_PER_NODE" \
        --disable-usage-stats --dashboard-host=0.0.0.0 --dashboard-port=8265
fi

RAY_ADDRESS="${RAY_ADDRESS:-http://127.0.0.1:8265}"
NVLINK_COUNT="$(nvidia-smi topo -m 2>/dev/null | grep -o 'NV[0-9][0-9]*' | wc -l || true)"
if [[ "$NVLINK_COUNT" -gt 0 ]]; then HAS_NVLINK=1; else HAS_NVLINK=0; fi

source "${SLIME_DIR}/scripts/models/qwen3-30B-A3B.sh"

CKPT_ARGS=(
    --hf-checkpoint "$MODEL_DIR"
    --ref-load "$REF_LOAD"
    --load "$LOAD"
    --save "$SAVE"
    --save-interval "$SAVE_INTERVAL"
)

SFT_ARGS=(
    --rollout-function-path slime.rollout.sft_rollout.generate_rollout
    --prompt-data "$TRAIN_DATA"
    --input-key messages
    --tool-key tools
    --rollout-shuffle
    --num-epoch "$NUM_EPOCHS"
    --rollout-batch-size "$ROLLOUT_BATCH_SIZE"
    --global-batch-size "$GLOBAL_BATCH_SIZE"
    --loss-type sft_loss
    --loss-mask-type qwen3
    --calculate-per-token-loss
    --disable-compute-advantages-and-returns
    --debug-train-only
)

PERF_ARGS=(
    --seq-length "$MAX_SEQUENCE_LENGTH"
    --tensor-model-parallel-size 4
    --sequence-parallel
    --pipeline-model-parallel-size 1
    --context-parallel-size "$CONTEXT_PARALLEL_SIZE"
    --expert-model-parallel-size 8
    --expert-tensor-parallel-size 1
    --recompute-granularity full
    --recompute-method uniform
    --recompute-num-layers 1
    --use-dynamic-batch-size
    --max-tokens-per-gpu "$MAX_TOKENS_PER_GPU"
)

OPTIMIZER_ARGS=(
    --optimizer adam
    --lr "$LEARNING_RATE"
    --lr-decay-style cosine
    --min-lr 1e-6
    --lr-warmup-fraction 0.1
    --weight-decay 0.1
    --adam-beta1 0.9
    --adam-beta2 0.98
    --use-distributed-optimizer
    --optimizer-cpu-offload
    --overlap-cpu-optimizer-d2h-h2d
    --use-precision-aware-optimizer
)

MISC_ARGS=(
    --attention-dropout 0.0
    --hidden-dropout 0.0
    --accumulate-allreduce-grads-in-fp32
    --attention-softmax-in-fp32
    --attention-backend flash
)

RUNTIME_ENV_JSON="{
  \"env_vars\": {
    \"PYTHONPATH\": \"${MEGATRON_DIR}\",
    \"CUDA_DEVICE_MAX_CONNECTIONS\": \"1\",
    \"NCCL_NVLS_ENABLE\": \"${HAS_NVLINK}\",
    \"MASTER_ADDR\": \"${MASTER_ADDR}\",
    \"PYTORCH_CUDA_ALLOC_CONF\": \"expandable_segments:True\"
  }
}"

ray job submit --address="$RAY_ADDRESS" \
    --runtime-env-json="$RUNTIME_ENV_JSON" \
    -- python3 "${SLIME_DIR}/train_async.py" \
    --actor-num-nodes "$ACTOR_NUM_NODES" \
    --actor-num-gpus-per-node "$GPUS_PER_NODE" \
    "${MODEL_ARGS[@]}" \
    "${CKPT_ARGS[@]}" \
    "${SFT_ARGS[@]}" \
    "${OPTIMIZER_ARGS[@]}" \
    "${PERF_ARGS[@]}" \
    "${MISC_ARGS[@]}"
