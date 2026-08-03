# Batch SWE Runs

Run on the Linux Docker host. `cc/claude` and the prompt file
`prompts/<INSTANCE_ID>.md` must exist.

Create a config file with one task per line:

```text
# INSTANCE_ID MODEL_NAME TOKEN IMAGE
django__django-11099 qwen3-coder-30b-a3b-via-claude-code token-001 swebench/sweb.eval.x86_64.django_1776_django-11099:latest
```

Start with at most five concurrent tasks:

```bash
bash launch_swe_batch.sh config.txt
```

Change concurrency when needed:

```bash
MAX_JOBS=4 bash launch_swe_batch.sh config.txt
```

Results are written to `runs/<INSTANCE_ID>/`.

Merge the per-instance prediction shards before running the SWE-bench harness:

```bash
python merge_predictions.py --runs-dir runs --output predictions.jsonl
```

The command replaces an existing output file, but never an input shard.
