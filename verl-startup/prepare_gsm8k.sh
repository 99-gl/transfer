#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="${DATA_DIR:-$HOME/data/gsm8k}"

python3 examples/data_preprocess/gsm8k.py \
  --local_dir "$DATA_DIR"
