#!/usr/bin/env bash
# Run one SWE-bench task on a Linux server.

set -euo pipefail

if [[ $# -ne 0 ]]; then
  cat >&2 <<'EOF'
Usage: bash launch_swe_container.sh

Override defaults with environment variables: IMAGE, INSTANCE_ID, PROMPT_FILE,
OUTPUT_DIR, and MODEL_NAME.
EOF
  exit 2
fi

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
image=${IMAGE:-swebench/sweb.eval.x86_64.django_1776_django-11099:latest}
instance_id=${INSTANCE_ID:-django__django-11099}
prompt_file=${PROMPT_FILE:-"$script_dir/prompts/$instance_id.md"}
output_dir=${OUTPUT_DIR:-"$script_dir/runs/$instance_id"}
model_name=${MODEL_NAME:-qwen3-coder-30b-a3b-via-claude-code}

[[ -f $prompt_file ]] || { echo "prompt not found: $prompt_file" >&2; exit 2; }
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
    RUNNER_PYTHON=$(type -P python || true)
    [ -n "$RUNNER_PYTHON" ] || { echo "python interpreter not found" >&2; exit 127; }
    export RUNNER_PYTHON
    exec su --preserve-environment -s /bin/bash agent <<"AGENT_COMMAND"
export HOME=/home/agent
export PATH=/cc:$PATH
exec "$RUNNER_PYTHON" /runner/run_instance.py \
  --instance-id "$INSTANCE_ID" \
  --prompt-file /input/task.md \
  --model-name "$MODEL_NAME" \
  --output-dir /output
AGENT_COMMAND
  '
