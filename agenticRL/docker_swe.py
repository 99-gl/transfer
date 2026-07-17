"""Docker evaluator for the upstream coding-agent SWE task layer.

All metadata parsing, workspace preparation, diff collection, and test runners
are deliberately reused from ``examples.coding_agent_rl.swe``.  Only the
fresh-evaluator sandbox changes from E2B to Docker.
"""

from __future__ import annotations

import logging

from examples.coding_agent_rl import swe as upstream
from slime.agent import sandbox as agent_sandbox

from .docker_sandbox import DockerSandbox

logger = logging.getLogger(__name__)

SWE_PROMPT = upstream.SWE_PROMPT
get_metadata = upstream.get_metadata
prepare_workspace = upstream.prepare_workspace
git_diff = upstream.git_diff


async def evaluate(
    *,
    image: str,
    workdir: str,
    diff_text: str,
    swepro: dict | None = None,
    eval_cmd: str | None = None,
    f2p_script: str | None = None,
    pre_commands: list[str] | str | None = None,
    timeout_sec: int = 600,
) -> tuple[float, bool]:
    """Grade a diff in a clean Docker container from the task image."""
    if not (swepro or eval_cmd or f2p_script):
        logger.warning("[docker.evaluate] no swepro/eval_cmd/f2p_script; reward=0")
        return 0.0, True

    async with DockerSandbox(image) as ev:
        await agent_sandbox.ensure_agent_user(ev, workdir)
        if swepro:
            await upstream._setup_swepro_assets(ev, swepro)
            await upstream.apply_before_repo_set_cmd(ev, workdir, swepro)
        if pre_commands:
            await upstream.apply_pre_commands(ev, workdir, pre_commands)

        applied = await upstream._apply_diff(ev, workdir, diff_text)
        if not applied:
            return 0.0, False
        if swepro:
            reward, _ = await upstream._run_swepro(ev, workdir, swepro, timeout_sec)
        elif eval_cmd:
            reward, _ = await upstream._run_eval_cmd(ev, workdir, eval_cmd, timeout_sec)
        else:
            reward, _ = await upstream._run_f2p_script(ev, workdir, f2p_script, timeout_sec)
        return reward, True
