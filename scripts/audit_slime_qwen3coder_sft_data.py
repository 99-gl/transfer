r"""Check Slime's Qwen3 multi-turn loss mask against the Qwen3-Coder template.

Usage (Linux shell, inside the official Slime image):
    PYTHONPATH=/root/slime python sweTrain/scripts/audit_slime_qwen3coder_sft_data.py \
      /data/swesmith_claude_code.jsonl \
      --model /data/models/Qwen3-Coder-30B-A3B-Instruct \
      --report /data/slime_audit.json \
      --errors /data/slime_audit_errors.jsonl

This is the Slime-specific complement to audit_qwen3coder_sft_data.py. It
requires the official Slime image (or an equivalent Slime checkout) and checks
that MultiTurnLossMaskGenerator(type=qwen3) returns exactly the same token
sequence as Qwen3-Coder's full chat template. It also checks the mask length,
that every assistant turn has a supervised span, and reports all failures in a
JSONL format that filter_sft_rows_by_errors.py can consume.

The input is read only. The model must be the exact checkpoint used for SFT.
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


class ValidationError(ValueError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Converted JSONL dataset.")
    parser.add_argument("--model", required=True, help="Local path or Hugging Face id of the training checkpoint.")
    parser.add_argument("--report", type=Path, help="Write the compact JSON summary to this path.")
    parser.add_argument("--errors", type=Path, help="Write one compact JSON diagnostic per invalid input row.")
    parser.add_argument("--max-errors", type=int, default=20, help="Maximum diagnostics retained (default: 20).")
    parser.add_argument("--limit", type=int, help="Audit only this many non-empty rows. Omit for all rows.")
    return parser.parse_args()


def diagnostic(row: int, instance_id: Any, category: str, detail: str) -> dict[str, Any]:
    return {"row": row, "instance_id": instance_id, "category": category, "detail": detail}


def as_token_list(value: Any) -> list[int]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, list) and value and isinstance(value[0], list):
        if len(value) != 1:
            raise ValidationError("chat template unexpectedly returned a batch of token sequences")
        value = value[0]
    if not isinstance(value, list) or not all(isinstance(token, int) for token in value):
        raise ValidationError("chat template did not return a token-id list")
    return value


def validate_row(row: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    if not isinstance(row, dict):
        raise ValidationError("top-level value must be an object")
    messages = row.get("messages")
    tools = row.get("tools")
    if not isinstance(messages, list) or not messages:
        raise ValidationError("messages must be a non-empty list")
    if not isinstance(tools, list):
        raise ValidationError("tools must be a list")
    assistant_turns = 0
    for index, message in enumerate(messages):
        if not isinstance(message, dict) or not isinstance(message.get("role"), str):
            raise ValidationError(f"message {index} must be an object with a role")
        if not isinstance(message.get("content"), str):
            raise ValidationError(f"message {index} content must be a string")
        if message["role"] == "assistant":
            assistant_turns += 1
    return messages, tools, assistant_turns


def main() -> int:
    args = parse_args()
    if not args.input.is_file():
        raise SystemExit(f"input file does not exist: {args.input}")

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    mask_generator = MultiTurnLossMaskGenerator(tokenizer, tokenizer_type="qwen3")
    totals: Counter[str] = Counter()
    diagnostics: list[dict[str, Any]] = []

    error_destination = None
    if args.errors:
        args.errors.parent.mkdir(parents=True, exist_ok=True)
        error_destination = args.errors.open("w", encoding="utf-8")
    try:
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
                    instance_id = row.get("instance_id") if isinstance(row, dict) else None
                    messages, tools, assistant_turns = validate_row(row)
                    expected_ids = as_token_list(
                        tokenizer.apply_chat_template(messages, tools=tools, tokenize=True, return_dict=False)
                    )
                    token_ids, loss_mask = mask_generator.get_loss_mask(messages, tools=tools)
                    token_ids = as_token_list(token_ids)
                    if token_ids != expected_ids:
                        raise ValidationError("Slime token sequence differs from the full Qwen3-Coder chat-template sequence")
                    if len(loss_mask) != len(expected_ids):
                        raise ValidationError("loss mask length differs from rendered token length")
                    if not all(mask in (0, 1) for mask in loss_mask):
                        raise ValidationError("loss mask contains values other than 0 or 1")

                    supervised_tokens = sum(loss_mask)
                    selected_spans = mask_generator.get_text_from_loss_mask(token_ids, loss_mask)
                    if assistant_turns and supervised_tokens == 0:
                        raise ValidationError("assistant turns exist but Slime supervises zero tokens")
                    if len(selected_spans) != assistant_turns:
                        raise ValidationError(
                            f"expected {assistant_turns} supervised assistant span(s), found {len(selected_spans)}"
                        )

                    totals["valid_rows"] += 1
                    totals["assistant_turns"] += assistant_turns
                    totals["rendered_tokens"] += len(expected_ids)
                    totals["supervised_tokens"] += supervised_tokens
                except Exception as exc:  # Continue to identify independent failures in later trajectories.
                    totals["invalid_rows"] += 1
                    item = diagnostic(row_number, instance_id, type(exc).__name__, str(exc))
                    if error_destination:
                        error_destination.write(json.dumps(item, ensure_ascii=False) + "\n")
                    if len(diagnostics) < args.max_errors:
                        diagnostics.append(item)
    finally:
        if error_destination:
            error_destination.close()

    summary = {
        "input": str(args.input),
        "model": args.model,
        "loss_mask_type": "qwen3",
        "rows_seen": totals["rows_seen"],
        "valid_rows": totals["valid_rows"],
        "invalid_rows": totals["invalid_rows"],
        "assistant_turns": totals["assistant_turns"],
        "rendered_tokens": totals["rendered_tokens"],
        "supervised_tokens": totals["supervised_tokens"],
        "diagnostics_shown": diagnostics,
    }
    output = json.dumps(summary, ensure_ascii=False, indent=2)
    print(output)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output + "\n", encoding="utf-8")
    return 1 if totals["invalid_rows"] else 0


if __name__ == "__main__":
    sys.exit(main())
