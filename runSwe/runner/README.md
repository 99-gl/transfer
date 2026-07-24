# SWE Task Runner

`run_instance.py` runs one SWE-bench task inside its task container. It invokes
Claude Code in `/testbed`, then stages all resulting changes and converts the
staged binary diff into a one-line SWE-bench prediction.

The runner must execute in the same container and filesystem as `/testbed`.
Mount its code read-only and mount an output directory writable by the container
user. Use a dedicated output directory for each run (or one already writable by
the container user); prompts are per-instance inputs and should be mounted
separately, read-only.

For a host-side Docker entry point that performs these mounts and switches to an
`agent` user after giving it ownership of `/testbed`, use
`../launch_swe_container.sh IMAGE INSTANCE_ID PROMPT_FILE OUTPUT_DIR MODEL_NAME`.
It mounts `../cc` at `/cc` and passes through `ANTHROPIC_BASE_URL`,
`ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_API_KEY`, and `ANTHROPIC_MODEL` from the
Linux server environment.

```bash
python /runner/run_instance.py \
  --instance-id django__django-11001 \
  --prompt-file /input/task.md \
  --model-name qwen3-coder-30b-a3b-via-claude-code \
  --output-dir /output
```

Use `--claude-arg=VALUE` repeatedly for Claude Code options required by the
container setup. The runner does not enable any permission-bypass option itself.

For example, the host can make these paths available to the task container:

```bash
docker run --rm \
  -v "$PWD/transfer/runSwe/runner:/runner:ro" \
  -v "$PROMPT_FILE:/input/task.md:ro" \
  -v "$OUTPUT_DIR:/output" \
  your-swe-task-image \
  python /runner/run_instance.py \
    --instance-id "$INSTANCE_ID" \
    --prompt-file /input/task.md \
    --model-name qwen3-coder-30b-a3b-via-claude-code \
    --output-dir /output
```

The mounted output directory receives:

```text
/output/
  logs/<instance_id>.stdout.log
  logs/<instance_id>.stderr.log
  logs/<instance_id>.git-add.stdout.log
  logs/<instance_id>.git-add.stderr.log
  logs/<instance_id>.git-diff.stderr.log
  logs/<instance_id>.git-diff-check.log
  metadata/<instance_id>.json
  predictions/<instance_id>.jsonl
```

The prediction JSONL contains only the standard SWE-bench fields:

```json
{"instance_id":"...","model_name_or_path":"...","model_patch":"..."}
```

The runner always attempts `git add -A` and `git diff --cached --binary` after
Claude Code exits, including when Claude exits nonzero. It returns Claude's exit
code when patch extraction and `git diff --cached --check` both succeed. It
returns `3` when the staged diff fails whitespace validation and `70` when git
postprocessing fails. Consult the metadata file to distinguish an agent failure
from a runner failure.
