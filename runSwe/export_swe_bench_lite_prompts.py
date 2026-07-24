#!/usr/bin/env python3
"""Export SWE-bench Lite prompts to ``transfer/runSwe/prompts``.

Usage:
    python export_swe_bench_lite_prompts.py --instance-id django__django-11099
    python export_swe_bench_lite_prompts.py --instance-id ID_ONE --instance-id ID_TWO
    python export_swe_bench_lite_prompts.py --slice 0:10

Exactly one selection method is required. The dataset split is always ``test``.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any


DATASET_NAME = "princeton-nlp/SWE-bench_Lite"
DATASET_SPLIT = "test"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "prompts"


def parse_slice(value: str) -> slice:
    """Parse a Python slice expression such as ``10:20:2``."""
    if not value or value.count(":") not in (1, 2):
        raise argparse.ArgumentTypeError(
            "--slice must be a Python slice such as '0:10', '10:', or '::2'"
        )

    parts = value.split(":")
    parts.extend([""] * (3 - len(parts)))
    try:
        start, stop, step = (int(part) if part else None for part in parts)
        result = slice(start, stop, step)
        if result.step == 0:
            raise ValueError("slice step cannot be zero")
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "--slice components must be integers, and the step cannot be zero"
        ) from error
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export English coding-agent prompts for SWE-bench Lite instances."
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--instance-id",
        action="append",
        metavar="ID",
        help="Select one instance; repeat this option to select multiple instances.",
    )
    selection.add_argument(
        "--slice",
        dest="instance_slice",
        type=parse_slice,
        metavar="START:STOP[:STEP]",
        help="Select dataset positions with Python slice syntax (for example, '0:5').",
    )
    return parser


def required_text(record: dict[str, Any], field: str) -> str:
    value = record.get(field)
    if value is None:
        raise ValueError(f"instance {record.get('instance_id', '<unknown>')!r} lacks {field!r}")
    return str(value)


def render_prompt(record: dict[str, Any]) -> str:
    """Render only task metadata; patch and test_patch are intentionally excluded."""
    instance_id = required_text(record, "instance_id")
    repo = required_text(record, "repo")
    base_commit = required_text(record, "base_commit")
    version = required_text(record, "version")
    problem_statement = required_text(record, "problem_statement").strip()
    hints_text = str(record.get("hints_text") or "").strip()

    sections = [
        "# SWE-bench Lite Coding Task",
        "",
        "You are a coding agent working in `/testbed`.",
        "",
        "## Instance Metadata",
        "",
        f"- **instance_id:** `{instance_id}`",
        f"- **repo:** `{repo}`",
        f"- **base_commit:** `{base_commit}`",
        f"- **version:** `{version}`",
        "",
        "## Problem Statement",
        "",
        problem_statement,
    ]
    if hints_text:
        sections.extend(["", "## Hints", "", hints_text])
    sections.extend(
        [
            "",
            "## Execution Rules",
            "",
            "Work only in `/testbed`. The repository is already prepared for this task.",
            "Treat `base_commit` as metadata; do not commit, reset, checkout, clean, or discard changes.",
            "",
            "1. Inspect the relevant source code and existing tests. Reproduce the reported behavior",
            "   with a focused command when feasible.",
            "2. Make the smallest necessary production/source-code fix.",
            "   Do not modify, add, delete, rename, or weaken any test files.",
            "3. Run the most relevant targeted tests.",
            "4. Before finishing, run `git diff --check`.",
            "",
            "When finished, leave all intended source changes in the git working tree.",
            "Do not use, inspect, search for, or apply any reference patch, gold patch, or test patch.",
            "Do not use the dataset `patch` or `test_patch` fields.",
            "",
        ]
    )
    return "\n".join(sections)


def select_records(dataset: Any, args: argparse.Namespace) -> list[dict[str, Any]]:
    records = [dict(record) for record in dataset]
    if args.instance_slice is not None:
        return records[args.instance_slice]
    if args.instance_id:
        requested = set(args.instance_id)
        found = {str(record.get("instance_id")) for record in records}
        missing = requested - found
        if missing:
            raise ValueError("unknown instance ID(s): " + ", ".join(sorted(missing)))
        return [record for record in records if str(record.get("instance_id")) in requested]
    return records


def output_name(instance_id: str) -> str:
    safe_id = re.sub(r"[^A-Za-z0-9._-]+", "_", instance_id).strip("._")
    return f"{safe_id or 'instance'}.md"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from datasets import load_dataset
    except ImportError:
        print("The 'datasets' package is required. Install it with: pip install datasets", file=sys.stderr)
        return 2

    try:
        dataset = load_dataset(DATASET_NAME, split=DATASET_SPLIT)
        records = select_records(dataset, args)
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        for record in records:
            instance_id = required_text(record, "instance_id")
            destination = DEFAULT_OUTPUT_DIR / output_name(instance_id)
            destination.write_text(render_prompt(record), encoding="utf-8")
            print(destination)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
