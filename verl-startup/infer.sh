MODEL_PATH=/path/to/qwen3-4b

CUDA_VISIBLE_DEVICES=6,7 \
vllm serve "$MODEL_PATH" \
  --data-parallel-size 2 \
  --host 0.0.0.0 \
  --port 8000 \
  --gpu-memory-utilization 0.8