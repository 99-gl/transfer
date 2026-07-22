"""Expose Slime's Anthropic-compatible adapter for a local SGLang server.

Claude Code sends Anthropic Messages API requests to this process.  The adapter
renders them with the local model tokenizer, forwards token IDs to SGLang's
``/generate`` endpoint, and translates the reply back to Anthropic's wire
format.  It is intended for trusted, private Docker networks only.
"""

from __future__ import annotations

import logging
import os
import signal
import threading

from slime.agent.adapters import AnthropicAdapter
from slime.agent.aiohttp_threaded import run_app_in_thread
from slime.utils.processing_utils import load_tokenizer


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set")
    return value


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

    model_path = required_env("MODEL_PATH")
    sglang_url = required_env("SGLANG_URL")
    bind_host = os.environ.get("ADAPTER_BIND_HOST", "0.0.0.0")
    port = int(os.environ.get("ADAPTER_PORT", "18001"))

    adapter = AnthropicAdapter(
        tokenizer=load_tokenizer(model_path, trust_remote_code=True),
        sglang_url=sglang_url,
        tool_parser=os.environ.get("SGLANG_TOOL_CALL_PARSER", "qwen3_coder"),
        reasoning_parser=os.environ.get("SGLANG_REASONING_PARSER", "qwen3"),
    )
    handle = run_app_in_thread(adapter.app, host=bind_host, port=port, thread_name="anthropic-adapter")
    logging.info("Anthropic adapter listening on http://%s:%d; upstream=%s", bind_host, handle.port, sglang_url)

    stopped = threading.Event()

    def stop(_signum: int, _frame: object) -> None:
        stopped.set()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        stopped.wait()
    finally:
        handle.stop()


if __name__ == "__main__":
    main()
