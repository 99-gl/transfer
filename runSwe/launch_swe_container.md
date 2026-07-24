# Launch SWE Task Container

Run this on the Linux server after exporting the Qwen/Anthropic-compatible
connection variables:

```bash
export ANTHROPIC_BASE_URL=...
export ANTHROPIC_AUTH_TOKEN=...
export ANTHROPIC_MODEL=...

bash launch_swe_container.sh
```

Defaults are the Django `django__django-11099` example, its matching image,
`prompts/<instance_id>.md`, `runs/<instance_id>`, and
`qwen3-coder-30b-a3b-via-claude-code`. Override any default per run, for example:

```bash
INSTANCE_ID=sympy__sympy-12345 \
IMAGE=swebench/sweb.eval.x86_64.sympy_...:latest \
bash launch_swe_container.sh
```

The script requires `cc/claude`, mounts it at `/cc`, and adds `/cc` to `PATH`.
It mounts the prompt at `/input/task.md`, the runner at `/runner`, and the
result directory at `/output`. Inside the container it gives `agent` ownership
of `/testbed` and starts the runner.

Results are written under `OUTPUT_DIR/predictions`, `OUTPUT_DIR/logs`, and
`OUTPUT_DIR/metadata`.
