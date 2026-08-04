"""Append-only, per-trajectory JSONL storage."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any


class JsonlRecorder:
    """Persist completed turns in one JSONL file per opaque trajectory ID.

    The lock makes multiple concurrent HTTP requests safe. Files are opened for
    a single append and flushed immediately, so a completed turn survives a
    process crash without a separate session-finalization step.
    """

    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.trajectories_dir = self.output_dir / "trajectories"
        self.trajectories_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._turn_counts: dict[str, int] = {}

    def path_for_trajectory(self, trajectory_id: str) -> Path:
        return self.trajectories_dir / f"{trajectory_id}.jsonl"

    async def write(self, trajectory_id: str, record: dict[str, Any]) -> int:
        """Append a turn and return its one-based trajectory-local turn index."""
        path = self.path_for_trajectory(trajectory_id)
        async with self._lock:
            if trajectory_id not in self._turn_counts:
                self._turn_counts[trajectory_id] = 0
                if path.exists():
                    with path.open("r", encoding="utf-8") as existing:
                        self._turn_counts[trajectory_id] = sum(1 for item in existing if item.strip())
            self._turn_counts[trajectory_id] += 1
            turn_index = self._turn_counts[trajectory_id]
            line = json.dumps({"turn_index": turn_index, **record}, ensure_ascii=False, separators=(",", ":"), default=str) + "\n"
            with path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line)
                handle.flush()
        return turn_index
