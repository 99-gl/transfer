"""Use Slime's Claude Code rollout with Docker instead of E2B.

This module patches only the two provider-specific globals before exporting the
upstream custom-generate function.  Slime's adapters, trajectory token capture,
Claude Code harness, and task orchestration remain upstream code.
"""

from examples.coding_agent_rl import generate as upstream

from . import docker_swe
from .docker_sandbox import DockerSandbox

upstream.E2BSandbox = DockerSandbox
upstream.swe = docker_swe

generate = upstream.generate
