#!/usr/bin/env bash
#
# Usage (inside an ms-swift Linux Docker container with 8 x A100/H100 80GB GPUs):
#   cd /workspace/intern-hw
#   export MODEL_DIR=/models/Qwen3-Coder-30B-A3B-Instruct
#   export OUTPUT_DIR=/checkpoints/qwen3-coder-30b-a3b-swe-full-sft-32k
#   bash sweTrain/scripts/run_qwen3_coder_30b_a3b_sft_ms_swift.sh
#
# The image must contain transformers>=4.51, DeepSpeed, FlashAttention, and a
# liger-kernel version that supports Qwen3 MoE. The default 8-way sequence
# parallel group is also the ZeRO-3 group, so the effective global batch size
# is one complete trajectory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

: "${MODEL_DIR:?Set MODEL_DIR to the local Qwen3-Coder-30B-A3B-Instruct checkpoint.}"
: "${OUTPUT_DIR:?Set OUTPUT_DIR to an empty or writable checkpoint directory.}"

TRAIN_DATA="${TRAIN_DATA:-${REPO_ROOT}/sweTrain/data/train_data_ms_swift.jsonl}"
NPROC_PER_NODE="${NPROC_PER_NODE:-8}"
SEQUENCE_PARALLEL_SIZE="${SEQUENCE_PARALLEL_SIZE:-8}"
MAX_LENGTH="${MAX_LENGTH:-32768}"
NUM_TRAIN_EPOCHS="${NUM_TRAIN_EPOCHS:-1}"

[[ -d "${MODEL_DIR}" ]] || { echo "MODEL_DIR does not exist: ${MODEL_DIR}" >&2; exit 2; }
[[ "${NPROC_PER_NODE}" -eq "${SEQUENCE_PARALLEL_SIZE}" ]] || {
    echo "This single-node script requires NPROC_PER_NODE == SEQUENCE_PARALLEL_SIZE." >&2
    exit 2
}
[[ -f "${TRAIN_DATA}" ]] || { echo "TRAIN_DATA does not exist: ${TRAIN_DATA}" >&2; exit 2; }
command -v swift >/dev/null || { echo "The ms-swift CLI is not installed in this environment." >&2; exit 2; }

export PYTHONUNBUFFERED=1
export TOKENIZERS_PARALLELISM=false
export CELOSS_PARALLEL_SIZE="${CELOSS_PARALLEL_SIZE:-2048}"
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"

NPROC_PER_NODE="${NPROC_PER_NODE}" \
CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0,1,2,3,4,5,6,7}" \
swift sft \
    --model "${MODEL_DIR}" \
    --dataset "${TRAIN_DATA}" \
    --template qwen3_coder \
    --tuner_type full \
    --torch_dtype bfloat16 \
    --num_train_epochs "${NUM_TRAIN_EPOCHS}" \
    --per_device_train_batch_size 1 \
    --gradient_accumulation_steps 1 \
    --learning_rate 5e-6 \
    --lr_scheduler_type cosine \
    --warmup_ratio 0.05 \
    --max_length "${MAX_LENGTH}" \
    --truncation_strategy delete \
    --agent_template qwen3_coder \
    --loss_scale default \
    --padding_free true \
    --attn_impl flash_attn \
    --sequence_parallel_size "${SEQUENCE_PARALLEL_SIZE}" \
    --use_liger_kernel true \
    --use_logits_to_keep false \
    --deepspeed zero3 \
    --dataset_num_proc 4 \
    --dataloader_num_workers 4 \
    --logging_steps 1 \
    --save_strategy epoch \
    --save_total_limit 2 \
    --save_only_model true \
    --output_dir "${OUTPUT_DIR}" \
    --add_version false
