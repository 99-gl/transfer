#!/bin/bash

# vLLM Embedding 服务启动脚本
# 用于部署 BGE-M3 embedding 模型
# 硬件配置: A100-80GB

# 配置
MODEL_NAME="BAAI/bge-m3"
HOST="0.0.0.0"
PORT=8001
TENSOR_PARALLEL_SIZE=1  # A100-80GB 单卡足够
GPU_MEMORY_UTILIZATION=0.9  # A100 显存利用率可以开高
MAX_MODEL_LEN=8192  # BGE-M3 最大支持 8192
MAX_NUM_SEQS=256  # A100 可以支持更大的批处理

echo "Starting vLLM Embedding Server (Optimized for A100-80GB)..."
echo "Model: $MODEL_NAME"
echo "Host: $HOST"
echo "Port: $PORT"
echo "GPU Memory Utilization: ${GPU_MEMORY_UTILIZATION}"
echo "Max Batch Size: ${MAX_NUM_SEQS}"

# 启动 vLLM embedding 服务
vllm serve "$MODEL_NAME" \
  --host "$HOST" \
  --port "$PORT" \
  --task embedding \
  --tensor-parallel-size "$TENSOR_PARALLEL_SIZE" \
  --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
  --max-model-len "$MAX_MODEL_LEN" \
  --max-num-seqs "$MAX_NUM_SEQS" \
  --trust-remote-code \
  --disable-log-requests

# 参数说明：
# --gpu-memory-utilization 0.9: A100 显存充足，可以用到 90%
# --max-num-seqs 256: 增大批处理，提高吞吐量
# --max-model-len 8192: BGE-M3 支持的最大长度
# --disable-log-requests: 减少日志输出（可选）
