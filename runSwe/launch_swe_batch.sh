#!/usr/bin/env bash
# Usage:
#   MAX_JOBS=5 bash launch_swe_batch.sh CONFIG_FILE
#
# CONFIG_FILE format: one run per line: INSTANCE_ID MODEL_NAME TOKEN IMAGE

set -euo pipefail
set -m

[[ $# -eq 1 ]] || {
  echo "Usage: bash $0 CONFIG_FILE" >&2
  exit 2
}

config_file=$1
max_jobs=${MAX_JOBS:-5}
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
[[ -f $config_file ]] || { echo "config file not found: $config_file" >&2; exit 2; }
[[ $max_jobs =~ ^[1-9][0-9]*$ ]] || { echo 'MAX_JOBS must be a positive integer' >&2; exit 2; }

cleanup() {
  local pid

  trap - INT TERM EXIT
  while IFS= read -r pid; do
    kill -TERM -- "-$pid" 2>/dev/null || true
  done < <(jobs -pr)
  wait || true
}

trap 'cleanup; exit 130' INT TERM
trap cleanup EXIT

while read -r instance_id model_name auth_token image extra; do
  [[ -z ${instance_id:-} || $instance_id == \#* ]] && continue
  [[ -n ${model_name:-} && -n ${auth_token:-} && -n ${image:-} && -z ${extra:-} ]] || {
    echo 'Each line must be: INSTANCE_ID MODEL_NAME TOKEN IMAGE' >&2
    exit 2
  }

  while (( $(jobs -rp | wc -l) >= max_jobs )); do
    wait -n || true
  done

  INSTANCE_ID="$instance_id" MODEL_NAME="$model_name" \
    ANTHROPIC_AUTH_TOKEN="$auth_token" \
    IMAGE="$image" \
    bash "$script_dir/launch_swe_container.sh" &
done <"$config_file"

wait
