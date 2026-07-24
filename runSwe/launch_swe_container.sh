#!/usr/bin/env bash
# Run one SWE-bench task on a Linux server.

set -euo pipefail

if [[ $# -ne 5 ]]; then
  cat >&2 <<'EOF'
Usage: bash launch_swe_container.sh IMAGE INSTANCE_ID PROMPT_FILE OUTPUT_DIR MODEL_NAME
EOF
  exit 2
fi

image=$1
instance_id=$2
prompt_file=$3
output_dir=$4
model_name=$5

[[ -f $prompt_file ]] || { echo "prompt not found: $prompt_file" >&2; exit 2; }

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
cc_dir="$script_dir/cc"
[[ -d $cc_dir ]] || { echo "Claude Code directory not found: $cc_dir" >&2; exit 2; }
mkdir -p "$output_dir"
prompt_file=$(realpath "$prompt_file")
output_dir=$(realpath "$output_dir")

mounts=(
  --volume "$script_dir/runner:/runner:ro"
  --volume "$cc_dir:/cc:ro"
  --volume "$prompt_file:/input/task.md:ro"
  --volume "$output_dir:/output"
)

docker run --rm -it \
  --entrypoint /bin/bash \
  "${mounts[@]}" \
  --env "INSTANCE_ID=$instance_id" \
  --env "MODEL_NAME=$model_name" \
  --env ANTHROPIC_BASE_URL \
  --env ANTHROPIC_AUTH_TOKEN \
  --env ANTHROPIC_API_KEY \
  --env ANTHROPIC_MODEL \
  "$image" \
  -lc '
    set -eu
    id -u agent >/dev/null 2>&1 || useradd --create-home --shell /bin/bash agent
    chown -R agent:agent /testbed
    chown agent:agent /output
    exec su -s /bin/bash agent <<"AGENT_COMMAND"
export HOME=/home/agent
export PATH=/cc:\$PATH
exec python3 /runner/run_instance.py \
  --instance-id "$INSTANCE_ID" \
  --prompt-file /input/task.md \
  --model-name "$MODEL_NAME" \
  --output-dir /output
AGENT_COMMAND
  '
