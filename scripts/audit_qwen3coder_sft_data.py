r"""Validate multi-turn tool-use data against a real Qwen3-Coder tokenizer and Slime.

Usage (Linux shell):
    PYTHONPATH=/path/to/slime python sweTrain/scripts/audit_qwen3coder_sft_data.py \
      /data/swesmith_claude_code.jsonl \
      --model /data/models/Qwen3-Coder-30B-A3B-Instruct \
      --context-length 32768 \
      --report /data/sft_audit.json \
      --errors /data/sft_audit_errors.jsonl

Run this against the complete converted dataset before SFT.  It does not
modify the input.  It exits non-zero if a structural error, chat-template
rendering error, loss-mask mismatch, or over-length sample is found.

The tokenizer must be the exact checkpoint that will be used for training.
The script imports Slime's MultiTurnLossMaskGenerator, so set PYTHONPATH to
the Slime checkout (or run from that checkout) before invoking it.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from transformers import AutoTokenizer

from slime.utils.mask_utils import MultiTurnLossMaskGenerator


EXPECTED_TOOLS = {
    "Bash": {"required": {"command"}, "allowed": {"command", "timeout", "description", "run_in_background"}},
    "Read": {"required": {"file_path"}, "allowed": {"file_path", "offset", "limit"}},
    "Write": {"required": {"file_path", "content"}, "allowed": {"file_path", "content"}},
    "Edit": {"required": {"file_path", "old_string", "new_string"}, "allowed": {"file_path", "old_string", "new_string", "replace_all"}},
}


class ValidationError(ValueError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Converted JSONL with top-level messages and tools fields.")
    parser.add_argument("--model", required=True, help="Local path or Hugging Face id of the training checkpoint.")
    parser.add_argument("--context-length", type=int, required=True, help="Maximum complete-trajectory token length allowed for SFT.")
    parser.add_argument("--loss-mask-type", choices=("qwen3", "qwen3_5"), default="qwen3")
    parser.add_argument("--report", type=Path, help="Write the compact JSON summary to this path.")
    parser.add_argument("--errors", type=Path, help="Write one compact JSON diagnostic per invalid input row.")
    parser.add_argument("--max-errors", type=int, default=20, help="Maximum diagnostics printed and written (default: 20).")
    parser.add_argument("--limit", type=int, help="Audit only this many rows. Omit for the complete dataset.")
    return parser.parse_args()


def json_error(row_number: int, instance_id: Any, category: str, detail: str) -> dict[str, Any]:
    return {"row": row_number, "instance_id": instance_id, "category": category, "detail": detail}


def tool_name(tool: Any) -> str | None:
    if not isinstance(tool, dict):
        return None
    function = tool.get("function")
    return function.get("name") if isinstance(function, dict) else None


def validate_schema(tools: Any) -> None:
    if not isinstance(tools, list):
        raise ValidationError("top-level tools must be a list")
    names = [tool_name(tool) for tool in tools]
    if set(names) != set(EXPECTED_TOOLS) or len(names) != len(EXPECTED_TOOLS):
        raise ValidationError(f"tools must contain exactly {sorted(EXPECTED_TOOLS)}, got {names!r}")

    for tool in tools:
        function = tool.get("function")
        if tool.get("type") != "function" or not isinstance(function, dict):
            raise ValidationError("each tool must have type='function' and an object function")
        name = function["name"]
        parameters = function.get("parameters")
        if not isinstance(parameters, dict):
            raise ValidationError(f"tool {name!r} parameters must be an object")
        required = parameters.get("required", [])
        if not isinstance(required, list) or not set(EXPECTED_TOOLS[name]["required"]).issubset(required):
            raise ValidationError(f"tool {name!r} has unexpected required fields: {required!r}")


def validate_messages(messages: Any) -> tuple[Counter[str], Counter[str], int, int]:
    if not isinstance(messages, list) or not messages:
        raise ValidationError("messages must be a non-empty list")
    if messages[0].get("role") != "system":
        raise ValidationError("the first message must have role='system'")

    role_counts: Counter[str] = Counter()
    call_counts: Counter[str] = Counter()
    pending_results = 0
    assistant_turns = 0

    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise ValidationError(f"message {index} is not an object")
        role = message.get("role")
        if role not in {"system", "user", "assistant", "tool"}:
            raise ValidationError(f"message {index} has unsupported role {role!r}")
        if not isinstance(message.get("content"), str):
            raise ValidationError(f"message {index} content must be a string")
        role_counts[role] += 1

        if role == "assistant":
            if pending_results:
                raise ValidationError(f"assistant message {index} appears before {pending_results} tool result(s)")
            assistant_turns += 1
            calls = message.get("tool_calls", [])
            if not isinstance(calls, list):
                raise ValidationError(f"assistant message {index} tool_calls must be a list")
            pending_results += len(calls)
            for call in calls:
                if not isinstance(call, dict) or call.get("type") != "function":
                    raise ValidationError(f"assistant message {index} has a malformed tool call")
                function = call.get("function")
                if not isinstance(function, dict):
                    raise ValidationError(f"assistant message {index} tool call function must be an object")
                name = function.get("name")
                arguments = function.get("arguments")
                if name not in EXPECTED_TOOLS or not isinstance(arguments, dict):
                    raise ValidationError(f"assistant message {index} has invalid call {name!r}")
                missing = EXPECTED_TOOLS[name]["required"] - set(arguments)
                extra = set(arguments) - EXPECTED_TOOLS[name]["allowed"]
                if missing or extra:
                    raise ValidationError(f"assistant message {index} {name} arguments: missing={sorted(missing)}, extra={sorted(extra)}")
                if name == "Read":
                    for key in ("offset", "limit"):
                        if key in arguments and (not isinstance(arguments[key], int) or arguments[key] < 1):
                            raise ValidationError(f"assistant message {index} Read.{key} must be a positive integer")
                call_counts[name] += 1
        elif role == "tool":
            if set(message) != {"role", "content"}:
                raise ValidationError(f"tool message {index} must contain only role and content")
            if pending_results == 0:
                raise ValidationError(f"tool message {index} has no preceding unresolved call")
            pending_results -= 1
        elif pending_results:
            raise ValidationError(f"message {index} appears before {pending_results} tool result(s)")

    if pending_results:
        raise ValidationError(f"{pending_results} assistant tool call(s) have no subsequent tool result")
    return role_counts, call_counts, assistant_turns, role_counts["tool"]


def percentile(values: list[int], q: float) -> int:
    if not values:
        return 0
    values = sorted(values)
    index = round((len(values) - 1) * q)
    return values[index]


def main() -> int:
    args = parse_args()
    if args.context_length < 1:
        raise SystemExit("--context-length must be positive")
    if not args.input.is_file():
        raise SystemExit(f"input file does not exist: {args.input}")

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    mask_generator = MultiTurnLossMaskGenerator(tokenizer, tokenizer_type=args.loss_mask_type)

    totals: Counter[str] = Counter()
    roles: Counter[str] = Counter()
    calls: Counter[str] = Counter()
    token_lengths: list[int] = []
    diagnostics: list[dict[str, Any]] = []

    with args.input.open("r", encoding="utf-8") as source:
        for row_number, line in enumerate(source, 1):
            if args.limit is not None and totals["rows_seen"] >= args.limit:
                break
            if not line.strip():
                continue
            totals["rows_seen"] += 1
            instance_id = None
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValidationError("top-level value must be an object")
                instance_id = row.get("instance_id")
                messages = row.get("messages")
                tools = row.get("tools")
                validate_schema(tools)
                row_roles, row_calls, assistant_turns, tool_results = validate_messages(messages)
                roles.update(row_roles)
                calls.update(row_calls)
                totals["assistant_turns"] += assistant_turns
                totals["tool_results"] += tool_results

                expected_ids = tokenizer.apply_chat_template(messages, tools=tools, tokenize=True, return_dict=False)
                token_ids, loss_mask = mask_generator.get_loss_mask(messages, tools=tools)
                if token_ids != expected_ids:
                    raise ValidationError("Slime loss-mask token sequence differs from tokenizer.apply_chat_template output")
                if len(loss_mask) != len(expected_ids):
                    raise ValidationError("loss mask length differs from rendered token length")
                supervised = sum(loss_mask)
                if supervised == 0 and assistant_turns:
                    raise ValidationError("assistant turns exist but the loss mask supervises zero tokens")
                token_lengths.append(len(expected_ids))
                totals["supervised_tokens"] += supervised
                totals["rendered_tokens"] += len(expected_ids)
                if len(expected_ids) > args.context_length:
                    totals["over_context_rows"] += 1
                    raise ValidationError(f"rendered length {len(expected_ids)} exceeds context length {args.context_length}")
                totals["valid_rows"] += 1
            except Exception as exc:  # Keep auditing later rows after a malformed trajectory.
                totals["invalid_rows"] += 1
                if len(diagnostics) < args.max_errors:
                    diagnostics.append(json_error(row_number, instance_id, type(exc).__name__, str(exc)))

    summary = {
        "input": str(args.input),
        "model": args.model,
        "loss_mask_type": args.loss_mask_type,
        "context_length": args.context_length,
        "rows_seen": totals["rows_seen"],
        "valid_rows": totals["valid_rows"],
        "invalid_rows": totals["invalid_rows"],
        "over_context_rows": totals["over_context_rows"],
        "roles": dict(sorted(roles.items())),
        "tool_calls": dict(sorted(calls.items())),
        "tool_results": totals["tool_results"],
        "assistant_turns": totals["assistant_turns"],
        "rendered_tokens": totals["rendered_tokens"],
        "supervised_tokens": totals["supervised_tokens"],
        "token_length": {
            "min": min(token_lengths, default=0),
            "p50": percentile(token_lengths, 0.50),
            "p95": percentile(token_lengths, 0.95),
            "p99": percentile(token_lengths, 0.99),
            "max": max(token_lengths, default=0),
        },
        "diagnostics_shown": diagnostics,
    }
    rendered_summary = json.dumps(summary, ensure_ascii=False, indent=2)
    print(rendered_summary)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered_summary + "\n", encoding="utf-8")
    if args.errors:
        args.errors.parent.mkdir(parents=True, exist_ok=True)
        with args.errors.open("w", encoding="utf-8") as destination:
            for diagnostic in diagnostics:
                destination.write(json.dumps(diagnostic, ensure_ascii=False) + "\n")

    if totals["invalid_rows"] or totals["over_context_rows"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
