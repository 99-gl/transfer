#!/usr/bin/env python3
"""Merge per-instance SWE-bench prediction shards into one JSONL file.

Usage:
    python merge_predictions.py --runs-dir runs
    python merge_predictions.py --runs-dir /data/swe/runs --output /data/swe/predictions.jsonl

The input layout must be ``<runs-dir>/<instance_id>/predictions/*.jsonl``.
The output uses the standard SWE-bench prediction fields and can be passed to
``python -m swebench.harness.run_evaluation --predictions_path``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterator


REQUIRED_FIELDS = ("instance_id", "model_name_or_path", "model_patch")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Merge runs/<instance_id>/predictions/*.jsonl into one SWE-bench JSONL file."
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=Path("runs"),
        help="Directory containing per-instance run directories (default: %(default)s).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Destination JSONL path (default: <runs-dir>/predictions.jsonl).",
    )
    return parser


def prediction_files(runs_dir: Path) -> list[Path]:
    return sorted(path for path in runs_dir.glob("*/predictions/*.jsonl") if path.is_file())


def read_records(path: Path) -> Iterator[dict[str, str]]:
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record: Any = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {error.msg}") from error
        if not isinstance(record, dict):
            raise ValueError(f"{path}:{line_number}: expected a JSON object")

        missing = [field for field in REQUIRED_FIELDS if field not in record]
        if missing:
            raise ValueError(f"{path}:{line_number}: missing required field(s): {', '.join(missing)}")
        if any(not isinstance(record[field], str) for field in REQUIRED_FIELDS):
            raise ValueError(f"{path}:{line_number}: all SWE-bench prediction fields must be strings")
        if not record["instance_id"]:
            raise ValueError(f"{path}:{line_number}: instance_id must not be empty")

        yield {field: record[field] for field in REQUIRED_FIELDS}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    runs_dir = args.runs_dir.resolve()
    if not runs_dir.is_dir():
        print(f"error: runs directory does not exist: {runs_dir}", file=sys.stderr)
        return 2

    output_path = (args.output or runs_dir / "predictions.jsonl").resolve()
    sources = prediction_files(runs_dir)
    if not sources:
        print(f"error: no files found under {runs_dir}/*/predictions/*.jsonl", file=sys.stderr)
        return 1
    if output_path in {source.resolve() for source in sources}:
        print("error: output path must not overwrite an input prediction shard", file=sys.stderr)
        return 2
    merged: list[dict[str, str]] = []
    seen_instances: dict[str, Path] = {}
    try:
        for source in sources:
            for record in read_records(source):
                instance_id = record["instance_id"]
                previous_source = seen_instances.get(instance_id)
                if previous_source is not None:
                    raise ValueError(
                        f"duplicate instance_id {instance_id!r} in {source} and {previous_source}"
                    )
                seen_instances[instance_id] = source
                merged.append(record)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as output_file:
        for record in merged:
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Merged {len(merged)} prediction record(s) from {len(sources)} shard(s): {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
