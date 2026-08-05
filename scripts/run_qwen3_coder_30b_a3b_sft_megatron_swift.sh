#!/usr/bin/env bash
#
# Usage (inside a Linux container with Megatron-SWIFT, Megatron-Core,
# mcore-bridge, Transformer Engine, Apex, and FlashAttention installed):
#   cd /workspace/intern-hw
#   export MODEL_DIR=/models/Qwen3-Coder-30B-A3B-Instruct
#   export OUTPUT_DIR=/checkpoints/qwen3-coder-30b-a3b-swe-full-sft-32k-mcore
#   bash transfer/scripts/run_qwen3_coder_30b_a3b_sft_megatron_swift.sh
#
# This script uses Megatron-SWIFT's mcore-bridge path: MODEL_DIR is the
# original Hugging Face checkpoint and does not need a separate conversion.
# It targets one 8 x A100/H100 80GB node. Checkpoints are saved as HF
# safetensors, so they can be loaded by the regular Swift/HF inference path.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

: "${MODEL_DIR:?Set MODEL_DIR to the local Qwen3-Coder-30B-A3B-Instruct checkpoint.}"
: "${OUTPUT_DIR:?Set OUTPUT_DIR to an empty or writable checkpoint directory.}"

TRAIN_DATA="${TRAIN_DATA:-${REPO_ROOT}/sweTrain/data/train_data_ms_swift.jsonl}"
NPROC_PER_NODE="${NPROC_PER_NODE:-8}"
TENSOR_PARALLEL_SIZE="${TENSOR_PARALLEL_SIZE:-4}"
CONTEXT_PARALLEL_SIZE="${CONTEXT_PARALLEL_SIZE:-2}"
EXPERT_PARALLEL_SIZE="${EXPERT_PARALLEL_SIZE:-8}"
MAX_LENGTH="${MAX_LENGTH:-32768}"
NUM_TRAIN_EPOCHS="${NUM_TRAIN_EPOCHS:-1}"
SAVE_STEPS="${SAVE_STEPS:-200}"

[[ -d "${MODEL_DIR}" ]] || { echo "MODEL_DIR does not exist: ${MODEL_DIR}" >&2; exit 2; }
[[ -f "${TRAIN_DATA}" ]] || { echo "TRAIN_DATA does not exist: ${TRAIN_DATA}" >&2; exit 2; }
[[ "${NPROC_PER_NODE}" -eq 8 ]] || {
    echo "This initial single-node configuration requires NPROC_PER_NODE=8." >&2
    exit 2
}
[[ "$((TENSOR_PARALLEL_SIZE * CONTEXT_PARALLEL_SIZE))" -eq "${NPROC_PER_NODE}" ]] || {
    echo "TENSOR_PARALLEL_SIZE * CONTEXT_PARALLEL_SIZE must equal NPROC_PER_NODE." >&2
    exit 2
}
[[ "$((MAX_LENGTH % CONTEXT_PARALLEL_SIZE))" -eq 0 ]] || {
    echo "MAX_LENGTH must be divisible by CONTEXT_PARALLEL_SIZE." >&2
    exit 2
}
command -v megatron >/dev/null || {
    echo "The Megatron-SWIFT CLI is not installed in this environment." >&2
    exit 2
}

export PYTHONUNBUFFERED=1
export TOKENIZERS_PARALLELISM=false
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"

NPROC_PER_NODE="${NPROC_PER_NODE}" \
CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0,1,2,3,4,5,6,7}" \
megatron sft \
    --model "${MODEL_DIR}" \
    --dataset "${TRAIN_DATA}" \
    --template qwen3_coder \
    --agent_template qwen3_coder \
    --tuner_type full \
    --bf16 true \
    --finetune true \
    --num_train_epochs "${NUM_TRAIN_EPOCHS}" \
    --micro_batch_size 1 \
    --global_batch_size 1 \
    --lr 5e-6 \
    --lr_decay_style cosine \
    --lr_warmup_fraction 0.05 \
    --min_lr 1e-6 \
    --max_length "${MAX_LENGTH}" \
    --truncation_strategy delete \
    --loss_scale default \
    --padding_free true \
    --tensor_model_parallel_size "${TENSOR_PARALLEL_SIZE}" \
    --context_parallel_size "${CONTEXT_PARALLEL_SIZE}" \
    --sequence_parallel true \
    --expert_model_parallel_size "${EXPERT_PARALLEL_SIZE}" \
    --expert_tensor_parallel_size 1 \
    --moe_token_dispatcher_type alltoall \
    --moe_grouped_gemm true \
    --moe_permute_fusion true \
    --moe_shared_expert_overlap true \
    --recompute_granularity full \
    --recompute_method uniform \
    --recompute_num_layers 1 \
    --cross_entropy_loss_fusion true \
    --attention_backend flash \
    --dataloader_num_workers 4 \
    --dataset_num_proc 4 \
    --logging_steps 1 \
    --save_steps "${SAVE_STEPS}" \
    --no_save_optim true \
    --no_save_rng true \
    --save_safetensors true \
    --output_dir "${OUTPUT_DIR}" \
    --add_version false
