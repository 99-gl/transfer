"""Summarize system-prompt variants in SWE-Smith trajectory JSONL/Parquet files.

The script intentionally prints only a short preview for each prompt so the
output stays small even when scanning a complete dataset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


def get_messages(record: dict[str, Any]) -> list[dict[str, Any]]:
    messages = record.get("messages", [])
    if isinstance(messages, str):
        messages = json.loads(messages)
    if not isinstance(messages, list):
        raise TypeError(f"messages must be a list or JSON string, got {type(messages).__name__}")
    return messages


def system_prompt(record: dict[str, Any]) -> str:
    systems = [m.get("content", "") for m in get_messages(record) if m.get("role") == "system"]
    if not systems:
        return "<NO_SYSTEM_MESSAGE>"
    if len(systems) != 1:
        return f"<SYSTEM_MESSAGE_COUNT={len(systems)}>"
    return systems[0] if isinstance(systems[0], str) else json.dumps(systems[0], ensure_ascii=False)


def iter_records(path: Path) -> Iterable[dict[str, Any]]:
    if path.suffix == ".jsonl":
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if line.strip():
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
        return

    if path.suffix == ".parquet":
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise SystemExit("Reading Parquet requires pyarrow: pip install pyarrow") from exc
        parquet_file = pq.ParquetFile(path)
        for batch in parquet_file.iter_batches(columns=["messages"]):
            for record in batch.to_pylist():
                yield record
        return

    raise ValueError(f"Unsupported input type: {path}")


def discover_inputs(inputs: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw_input in inputs:
        path = Path(raw_input)
        if path.is_dir():
            files.extend(sorted(p for p in path.rglob("*") if p.suffix in {".jsonl", ".parquet"}))
        elif path.suffix in {".jsonl", ".parquet"}:
            files.append(path)
        else:
            raise ValueError(f"Expected a .jsonl/.parquet file or directory: {path}")
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="JSONL/Parquet files or directories to scan")
    parser.add_argument("--preview-chars", type=int, default=240, help="Maximum prompt preview length")
    args = parser.parse_args()

    counts: Counter[str] = Counter()
    files_by_prompt: defaultdict[str, set[str]] = defaultdict(set)
    total = 0
    invalid = 0
    for path in discover_inputs(args.inputs):
        for record in iter_records(path):
            total += 1
            try:
                prompt = system_prompt(record)
            except (TypeError, ValueError, json.JSONDecodeError):
                invalid += 1
                prompt = "<INVALID_MESSAGES>"
            counts[prompt] += 1
            files_by_prompt[prompt].add(path.name)

    print(f"rows={total} prompt_variants={len(counts)} invalid_messages={invalid}")
    for index, (prompt, count) in enumerate(counts.most_common(), 1):
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
        compact = " ".join(prompt.split())
        if len(compact) > args.preview_chars:
            compact = compact[: args.preview_chars] + "..."
        source_files = sorted(files_by_prompt[prompt])
        source_preview = ",".join(source_files[:2])
        if len(source_files) > 2:
            source_preview += ",..."
        print(
            f"{index:02d} count={count} chars={len(prompt)} sha256={digest} "
            f"source_files={len(source_files)} examples={source_preview} preview={compact}"
        )


if __name__ == "__main__":
    main()
