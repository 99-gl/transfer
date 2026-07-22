"""Expose Slime's Anthropic-compatible adapter for a local SGLang server.

Claude Code sends Anthropic Messages API requests to this process.  The adapter
renders them with the local model tokenizer, forwards token IDs to SGLang's
``/generate`` endpoint, and translates the reply back to Anthropic's wire
format.  It is intended for trusted, private Docker networks only.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from slime.agent.adapters import AnthropicAdapter
from slime.agent.aiohttp_threaded import run_app_in_thread
from slime.utils.processing_utils import load_tokenizer


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set")
    return value


class TrajectoryLogger:
    """Append each completed Adapter turn to a JSONL file for inference debugging."""

    def __init__(self, path: str, tokenizer: Any) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.tokenizer = tokenizer
        self.lock = threading.Lock()

    def __call__(
        self,
        session_id: str,
        translated_messages: list[dict[str, Any]],
        tools_schema: list[dict[str, Any]] | None,
        adapter_response: dict[str, Any],
        turn: Any,
    ) -> None:
        output_ids = list(getattr(turn, "output_ids", []) or [])
        prompt_ids = list(getattr(turn, "prompt_ids", []) or [])
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "messages": translated_messages,
            "tools": tools_schema,
            "adapter_response": adapter_response,
            "finish_reason": getattr(turn, "finish_reason", None),
            "prompt_ids": prompt_ids,
            "output_ids": output_ids,
            "output_log_probs": list(getattr(turn, "output_log_probs", []) or []),
            "raw_output": self.tokenizer.decode(output_ids, skip_special_tokens=False),
        }
        line = json.dumps(record, ensure_ascii=False, default=str)
        with self.lock, self.path.open("a", encoding="utf-8") as log_file:
            log_file.write(line + "\n")
            log_file.flush()


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

    model_path = required_env("MODEL_PATH")
    sglang_url = required_env("SGLANG_URL")
    bind_host = os.environ.get("ADAPTER_BIND_HOST", "0.0.0.0")
    port = int(os.environ.get("ADAPTER_PORT", "18001"))
    trajectory_log_path = os.environ.get("TRAJECTORY_LOG_PATH", "/tmp/anthropic_adapter_trajectory.jsonl")
    tokenizer = load_tokenizer(model_path, trust_remote_code=True)
    trajectory_logger = TrajectoryLogger(trajectory_log_path, tokenizer)

    adapter = AnthropicAdapter(
        tokenizer=tokenizer,
        sglang_url=sglang_url,
        tool_parser=os.environ.get("SGLANG_TOOL_CALL_PARSER", "qwen3_coder"),
        reasoning_parser=os.environ.get("SGLANG_REASONING_PARSER", "qwen3"),
        debug_callback=trajectory_logger,
    )
    handle = run_app_in_thread(adapter.app, host=bind_host, port=port, thread_name="anthropic-adapter")
    logging.info("Anthropic adapter listening on http://%s:%d; upstream=%s", bind_host, handle.port, sglang_url)
    logging.info("Writing completed turns to %s", trajectory_log_path)

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
