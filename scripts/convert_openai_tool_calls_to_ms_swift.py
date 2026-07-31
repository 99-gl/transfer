#!/usr/bin/env python3
"""Convert OpenAI-style tool traces into the MS-Swift Agent SFT format.

Usage (Linux shell):
    python sweTrain/scripts/convert_openai_tool_calls_to_ms_swift.py \\
      sweTrain/data/train_data.jsonl \\
      sweTrain/data/train_data_ms_swift.jsonl

The input uses ``assistant.tool_calls``.  MS-Swift discards unknown message
keys during preprocessing, so tool calls must instead become standalone
``{"role": "tool_call", "content": ...}`` messages.  This program preserves
all other top-level fields and validates the tool-call/tool-result ordering.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


class ConversionError(ValueError):
    """An input trajectory cannot be represented by the MS-Swift Agent format."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='OpenAI-style JSONL source file.')
    parser.add_argument('output', type=Path, help='MS-Swift-compatible JSONL destination file.')
    parser.add_argument('--overwrite', action='store_true', help='Allow replacing an existing output file.')
    return parser.parse_args()


def tool_call_content(call: Any, row_number: int, message_number: int, call_number: int) -> str:
    if not isinstance(call, dict) or call.get('type') != 'function':
        raise ConversionError(f'row {row_number}, message {message_number}, call {call_number}: invalid tool call')
    function = call.get('function')
    if not isinstance(function, dict):
        raise ConversionError(f'row {row_number}, message {message_number}, call {call_number}: missing function')
    name = function.get('name')
    arguments = function.get('arguments')
    if not isinstance(name, str) or not name:
        raise ConversionError(f'row {row_number}, message {message_number}, call {call_number}: invalid function name')
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise ConversionError(
                f'row {row_number}, message {message_number}, call {call_number}: invalid JSON arguments') from exc
    if not isinstance(arguments, dict):
        raise ConversionError(
            f'row {row_number}, message {message_number}, call {call_number}: arguments must be an object')
    return json.dumps({'name': name, 'arguments': arguments}, ensure_ascii=False, separators=(',', ':'))


def convert_row(row: Any, row_number: int) -> tuple[dict[str, Any], Counter[str]]:
    if not isinstance(row, dict):
        raise ConversionError(f'row {row_number}: expected a JSON object')
    messages = row.get('messages')
    if not isinstance(messages, list) or not messages:
        raise ConversionError(f'row {row_number}: messages must be a non-empty list')

    output_messages: list[dict[str, str]] = []
    pending_tool_results = 0
    counts: Counter[str] = Counter()
    for message_number, message in enumerate(messages, 1):
        if not isinstance(message, dict):
            raise ConversionError(f'row {row_number}, message {message_number}: expected an object')
        role = message.get('role')
        content = message.get('content')
        if role not in {'system', 'user', 'assistant', 'tool'} or not isinstance(content, str):
            raise ConversionError(f'row {row_number}, message {message_number}: invalid role or content')

        if role == 'tool':
            if pending_tool_results == 0:
                raise ConversionError(f'row {row_number}, message {message_number}: unexpected tool result')
            output_messages.append({'role': 'tool', 'content': content})
            pending_tool_results -= 1
            counts['tool_results'] += 1
            continue

        if pending_tool_results:
            raise ConversionError(
                f'row {row_number}, message {message_number}: {pending_tool_results} tool result(s) missing')

        if role != 'assistant':
            output_messages.append({'role': role, 'content': content})
            continue

        calls = message.get('tool_calls')
        if calls is None:
            output_messages.append({'role': 'assistant', 'content': content})
            counts['assistant_messages'] += 1
            continue
        if not isinstance(calls, list) or not calls:
            raise ConversionError(f'row {row_number}, message {message_number}: tool_calls must be a non-empty list')

        # Keep any reasoning/text that precedes the calls as an assistant turn.
        if content:
            output_messages.append({'role': 'assistant', 'content': content})
            counts['assistant_messages'] += 1
        for call_number, call in enumerate(calls, 1):
            output_messages.append({
                'role': 'tool_call',
                'content': tool_call_content(call, row_number, message_number, call_number),
            })
            counts['tool_calls'] += 1
            pending_tool_results += 1

    if pending_tool_results:
        raise ConversionError(f'row {row_number}: {pending_tool_results} tool result(s) missing at end of trajectory')

    converted = dict(row)
    converted['messages'] = output_messages
    return converted, counts


def main() -> int:
    args = parse_args()
    if not args.input.is_file():
        raise SystemExit(f'input does not exist: {args.input}')
    if args.input.resolve() == args.output.resolve():
        raise SystemExit('input and output must be different files')
    if args.output.exists() and not args.overwrite:
        raise SystemExit(f'output already exists: {args.output}; pass --overwrite to replace it')

    args.output.parent.mkdir(parents=True, exist_ok=True)
    totals: Counter[str] = Counter()
    with args.input.open('r', encoding='utf-8') as source, args.output.open('w', encoding='utf-8', newline='\n') as dest:
        for row_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            converted, counts = convert_row(json.loads(line), row_number)
            dest.write(json.dumps(converted, ensure_ascii=False, separators=(',', ':')) + '\n')
            totals.update(counts)
            totals['rows'] += 1
    print(json.dumps(dict(sorted(totals.items())), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
