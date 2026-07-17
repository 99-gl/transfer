# Docker Claude Code rollout for Slime

This directory is an E2B-free, inference-only adaptation of Slime's
`examples/coding_agent_rl` example for `Qwen3-Coder-30B-A3B-Instruct`.
It deliberately does not change files under `slime/`.

## Files and upstream mapping

| This directory | Role | Upstream Slime file reused/replaced |
| --- | --- | --- |
| `docker_sandbox.py` | Docker implementation of the async sandbox protocol | `slime/slime/agent/sandbox.py` (`E2BSandbox`) |
| `docker_generate.py` | Changes the upstream rollout's sandbox/evaluator binding | `slime/examples/coding_agent_rl/generate.py` |
| `docker_swe.py` | Replaces the clean E2B evaluator container with Docker | `slime/examples/coding_agent_rl/swe.py` |
| `run_rollout_only_docker_qwen3_coder_30b_a3b.sh` | Single-node, no-training entry point | `slime/examples/coding_agent_rl/run_qwen36_35b_a3b_swe_8nodes.sh` |

The adapter, Claude Code harness, tool parsing, and token-correct trajectory
capture remain upstream: `slime/slime/agent/adapters/`,
`slime/slime/agent/harness/claude_code.py`, and
`slime/slime/agent/trajectory.py`.

## Host dependencies

Install these on every Ray worker that will execute a rollout:

1. NVIDIA driver/CUDA compatible with the installed PyTorch, SGLang, and the
   target GPU. The Qwen checkpoint is loaded by SGLang, not by Megatron in this
   rollout-only mode.
2. The Slime runtime plus its normal SGLang/Ray dependencies.
3. Docker Engine 20.10+ with the NVIDIA Container Toolkit only if the *task
   image itself* needs GPUs. Docker must be usable by the Unix user that runs
   Ray (`docker ps` must succeed without `sudo`).
4. Python Docker SDK in the Slime environment:
   `pip install -r transfer/agenticRL/requirements-docker.txt`.
5. A Linux x64 Node 22 tarball and the Linux x64 Claude Code npm tarball. The
   harness uploads and installs both into every disposable task container.
6. The Qwen3-Coder-30B-A3B-Instruct Hugging Face checkpoint on local storage.

No Anthropic API key, E2B key, or externally reachable Anthropic endpoint is
required. This rollout never calls the E2B SDK, although a full upstream Slime
installation may still include its optional `e2b` Python package. Claude Code
points at Slime's local Anthropic-compatible adapter using `ANTHROPIC_BASE_URL`.

## Task image requirements

`metadata.image` selects a Docker image, and `metadata.workdir` is the clean
repository path in that image. Each rollout starts two separate containers from
that same image: one for Claude Code and one for evaluation. Bake the following
into the image:

- `/bin/bash`, `git`, `tar`, `patch`, `runuser`/`util-linux`, `useradd`, and
  Python 3;
- a clean, uncommitted repository at `workdir`, with its test dependencies;
- any compiler, database client, service, fixture, or test runtime required by
  the selected task.

`Dockerfile.agent-runtime` is a base template, not a complete SWE image. The
repository and its dependencies must be added for the task being evaluated.

The host creates the `agent` user and installs Node/Claude Code after each
container starts. The task image therefore needs to run as root initially.

## Run one end-to-end smoke test

Start from `sample_task.jsonl`, replace its `image` and `workdir`, and use a
small task. On the Linux server:

```bash
cd /path/to/intern-hw
pip install -r transfer/agenticRL/requirements-docker.txt

export HF_CHECKPOINT=/models/Qwen3-Coder-30B-A3B-Instruct
export PROMPT_DATA=$PWD/transfer/agenticRL/sample_task.jsonl
export SLIME_AGENT_NODE_TARBALL=/artifacts/node-v22.*/node-v22.*-linux-x64.tar.xz
export SLIME_AGENT_CC_TARBALL=/artifacts/anthropic-ai-claude-code-local-linux-x64.tgz
export ROLLOUT_NUM_GPUS=4
export ROLLOUT_TP_SIZE=4
bash transfer/agenticRL/run_rollout_only_docker_qwen3_coder_30b_a3b.sh
```

The launcher uses `--debug-rollout-only`: it starts only SGLang and the rollout
manager. It does not initialize Megatron, load a reference checkpoint, compute
advantages, or update weights. Inspect `run.log` and
`runs/.../rollout_dumps/rollout_0.pt` after it completes.

## Networking

The adapter runs in the Ray worker process while Claude Code runs in a Docker
container. `DockerSandbox` maps `host.docker.internal` to Docker's
`host-gateway`; the launcher uses that host name by default. This is intended
for a single-node smoke test. On a multi-node Ray cluster, every worker must
run Docker and the adapter address must resolve back to the same worker that
started the task container. Retain `host.docker.internal` when Docker uses the
standard Linux bridge and the installed Docker supports `host-gateway`.

If the task image needs network access, configure it with
`SLIME_AGENT_DOCKER_NETWORK`. Do not use host networking by default: the
bridge keeps the task environment isolated while still allowing the explicit
adapter callback.
