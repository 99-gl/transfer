#!/usr/bin/env python3
"""Run Claude Code for one SWE-bench instance and export its patch as JSONL."""

import argparse
import json
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, TextIO


POSTPROCESSING_ERROR = 70
DIFF_CHECK_ERROR = 3
COMMAND_NOT_FOUND = 127


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Claude Code in one SWE task container and write a prediction JSONL shard."
    )
    parser.add_argument("--instance-id", required=True, help="SWE-bench instance ID.")
    parser.add_argument("--prompt-file", required=True, type=Path, help="Read-only Markdown prompt file.")
    parser.add_argument(
        "--model-name",
        required=True,
        help="Value written as model_name_or_path in the prediction.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Mounted result directory, for example /output.",
    )
    parser.add_argument(
        "--testbed",
        default="/testbed",
        type=Path,
        help="Task repository directory (default: %(default)s).",
    )
    parser.add_argument(
        "--claude-command",
        default="claude",
        help="Claude Code executable (default: %(default)s).",
    )
    parser.add_argument(
        "--claude-arg",
        action="append",
        default=[],
        help="Extra argument passed to Claude Code; repeat as needed.",
    )
    return parser


def tee_stream(source: TextIO, log: TextIO, console: TextIO) -> None:
    """Copy a child stream to its log and the corresponding runner console stream."""
    try:
        for chunk in iter(source.readline, ""):
            log.write(chunk)
            log.flush()
            console.write(chunk)
            console.flush()
    finally:
        source.close()


def run_claude(args: argparse.Namespace, stdout_path: Path, stderr_path: Path) -> int:
    prompt = args.prompt_file.read_text(encoding="utf-8")
    command = [args.claude_command, "-p", *args.claude_arg, prompt]
    try:
        with stdout_path.open("w", encoding="utf-8") as stdout_log, stderr_path.open(
            "w", encoding="utf-8"
        ) as stderr_log:
            process = subprocess.Popen(
                command,
                cwd=args.testbed,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            assert process.stdout is not None
            assert process.stderr is not None
            stdout_thread = threading.Thread(
                target=tee_stream, args=(process.stdout, stdout_log, sys.stdout), daemon=True
            )
            stderr_thread = threading.Thread(
                target=tee_stream, args=(process.stderr, stderr_log, sys.stderr), daemon=True
            )
            stdout_thread.start()
            stderr_thread.start()
            exit_code = process.wait()
            stdout_thread.join()
            stderr_thread.join()
            return exit_code
    except FileNotFoundError:
        message = f"runner error: Claude command not found: {args.claude_command}\n"
        stderr_path.write_text(message, encoding="utf-8")
        sys.stderr.write(message)
        return COMMAND_NOT_FOUND


def run_git(command: List[str], testbed: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=testbed,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.testbed.is_dir():
        print(f"runner error: testbed does not exist: {args.testbed}", file=sys.stderr)
        return POSTPROCESSING_ERROR
    if not args.prompt_file.is_file():
        print(f"runner error: prompt file does not exist: {args.prompt_file}", file=sys.stderr)
        return POSTPROCESSING_ERROR

    instance_file = safe_filename(args.instance_id) or "instance"
    logs_dir = args.output_dir / "logs"
    metadata_dir = args.output_dir / "metadata"
    predictions_dir = args.output_dir / "predictions"
    for directory in (logs_dir, metadata_dir, predictions_dir):
        directory.mkdir(parents=True, exist_ok=True)

    stdout_path = logs_dir / f"{instance_file}.stdout.log"
    stderr_path = logs_dir / f"{instance_file}.stderr.log"
    started_at = timestamp()
    claude_exit_code = run_claude(args, stdout_path, stderr_path)

    git_add = run_git(["git", "add", "-A"], args.testbed)
    write_text(logs_dir / f"{instance_file}.git-add.stdout.log", git_add.stdout)
    write_text(logs_dir / f"{instance_file}.git-add.stderr.log", git_add.stderr)

    cached_diff = run_git(["git", "diff", "--cached", "--binary"], args.testbed)
    write_text(logs_dir / f"{instance_file}.git-diff.stderr.log", cached_diff.stderr)

    diff_check = run_git(["git", "diff", "--cached", "--check"], args.testbed)
    diff_check_path = logs_dir / f"{instance_file}.git-diff-check.log"
    write_text(diff_check_path, diff_check.stdout + diff_check.stderr)

    prediction_path = predictions_dir / f"{instance_file}.jsonl"
    postprocessing_ok = git_add.returncode == 0 and cached_diff.returncode == 0
    if postprocessing_ok:
        prediction = {
            "instance_id": args.instance_id,
            "model_name_or_path": args.model_name,
            "model_patch": cached_diff.stdout,
        }
        write_text(prediction_path, json.dumps(prediction, ensure_ascii=False) + "\n")

    metadata = {
        "instance_id": args.instance_id,
        "model_name_or_path": args.model_name,
        "testbed": str(args.testbed),
        "prompt_file": str(args.prompt_file),
        "started_at": started_at,
        "finished_at": timestamp(),
        "claude_exit_code": claude_exit_code,
        "git_add_exit_code": git_add.returncode,
        "git_diff_cached_exit_code": cached_diff.returncode,
        "git_diff_check_exit_code": diff_check.returncode,
        "model_patch_bytes": len(cached_diff.stdout.encode("utf-8")),
        "prediction_path": str(prediction_path) if postprocessing_ok else None,
    }
    write_text(
        metadata_dir / f"{instance_file}.json",
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
    )

    if not postprocessing_ok:
        print("runner error: unable to stage or extract the cached git diff", file=sys.stderr)
        return POSTPROCESSING_ERROR
    if diff_check.returncode != 0:
        print("runner error: git diff --cached --check failed", file=sys.stderr)
        return DIFF_CHECK_ERROR
    return claude_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
