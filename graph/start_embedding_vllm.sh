#!/bin/bash

# vLLM Embedding 服务启动脚本
# 用于部署 BGE-M3 embedding 模型

# 配置
MODEL_NAME="BAAI/bge-m3"
HOST="0.0.0.0"
PORT=8001
TENSOR_PARALLEL_SIZE=1  # 如果有多张 GPU 可以增加

echo "Starting vLLM Embedding Server..."
echo "Model: $MODEL_NAME"
echo "Host: $HOST"
echo "Port: $PORT"

# 启动 vLLM embedding 服务
vllm serve "$MODEL_NAME" \
  --host "$HOST" \
  --port "$PORT" \
  --task embedding \
  --tensor-parallel-size "$TENSOR_PARALLEL_SIZE" \
  --trust-remote-code \
  --max-model-len 8192

# 参数说明：
# --task embedding: 指定为 embedding 任务
# --tensor-parallel-size: GPU 并行数量
# --trust-remote-code: 允许执行模型代码（某些模型需要）
# --max-model-len: 最大序列长度（可根据显存调整）
