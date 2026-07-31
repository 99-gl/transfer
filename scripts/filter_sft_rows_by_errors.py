r"""Remove JSONL samples selected by one or more audit error files.

Usage (Linux shell):
    python sweTrain/scripts/filter_sft_rows_by_errors.py \
      /data/swesmith_claude_code.jsonl \
      /data/swesmith_claude_code_filtered.jsonl \
      --errors /data/qwen_audit_errors.jsonl \
      --errors /data/slime_audit_errors.jsonl

The error files must be JSONL records containing ``row`` and/or
``instance_id``.  The generic Qwen tokenizer audit and the Slime loss-mask
audit both produce this format.  A sample is removed when either its physical
JSONL line number (``row``) or non-empty ``instance_id`` appears in any error
file.  This lets a later Slime audit be added without changing the initial
filtering workflow.

The input is never modified. The output path must be new unless --overwrite is
provided.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Source JSONL dataset.")
    parser.add_argument("output", type=Path, help="Filtered JSONL dataset to create.")
    parser.add_argument(
        "--errors",
        action="append",
        type=Path,
        required=True,
        help="Audit errors JSONL. Repeat --errors to combine generic and Slime audit results.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing an existing output file.")
    return parser.parse_args()


def load_selectors(paths: list[Path]) -> tuple[set[int], set[str], Counter[str]]:
    rows: set[int] = set()
    instance_ids: set[str] = set()
    stats: Counter[str] = Counter()

    for path in paths:
        if not path.is_file():
            raise ValueError(f"errors file does not exist: {path}")
        with path.open("r", encoding="utf-8") as source:
            for line_number, line in enumerate(source, 1):
                if not line.strip():
                    continue
                try:
                    record: Any = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid JSON in {path}:{line_number}: {exc}") from exc
                if not isinstance(record, dict):
                    raise ValueError(f"error record in {path}:{line_number} must be an object")

                found_selector = False
                row = record.get("row")
                if isinstance(row, int) and row > 0:
                    rows.add(row)
                    stats["row_selectors"] += 1
                    found_selector = True

                instance_id = record.get("instance_id")
                if isinstance(instance_id, str) and instance_id:
                    instance_ids.add(instance_id)
                    stats["instance_id_selectors"] += 1
                    found_selector = True

                if not found_selector:
                    raise ValueError(f"error record in {path}:{line_number} has neither a positive row nor a non-empty instance_id")
                stats["error_records"] += 1
    return rows, instance_ids, stats


def main() -> int:
    args = parse_args()
    if not args.input.is_file():
        raise SystemExit(f"input file does not exist: {args.input}")
    if args.input.resolve() == args.output.resolve():
        raise SystemExit("input and output paths must differ")
    if args.output.exists() and not args.overwrite:
        raise SystemExit(f"output already exists: {args.output}; add --overwrite to replace it")

    try:
        rejected_rows, rejected_instance_ids, selector_stats = load_selectors(args.errors)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    args.output.parent.mkdir(parents=True, exist_ok=True)
    stats: Counter[str] = Counter(selector_stats)
    with args.input.open("r", encoding="utf-8") as source, args.output.open("w", encoding="utf-8") as destination:
        for row_number, line in enumerate(source, 1):
            if not line.strip():
                stats["blank_input_lines"] += 1
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"invalid JSON in input at line {row_number}: {exc}") from exc
            if not isinstance(row, dict):
                raise SystemExit(f"input line {row_number} is not a JSON object")

            stats["input_samples"] += 1
            instance_id = row.get("instance_id")
            by_row = row_number in rejected_rows
            by_instance_id = isinstance(instance_id, str) and instance_id in rejected_instance_ids
            if by_row or by_instance_id:
                stats["removed_samples"] += 1
                if by_row:
                    stats["removed_by_row"] += 1
                if by_instance_id:
                    stats["removed_by_instance_id"] += 1
                continue

            destination.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            stats["kept_samples"] += 1

    summary = {
        "input": str(args.input),
        "output": str(args.output),
        "errors": [str(path) for path in args.errors],
        "error_records": stats["error_records"],
        "unique_rejected_rows": len(rejected_rows),
        "unique_rejected_instance_ids": len(rejected_instance_ids),
        "input_samples": stats["input_samples"],
        "kept_samples": stats["kept_samples"],
        "removed_samples": stats["removed_samples"],
        "removed_by_row": stats["removed_by_row"],
        "removed_by_instance_id": stats["removed_by_instance_id"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
