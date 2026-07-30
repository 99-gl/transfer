r"""Map converted SWE-Smith trajectories to the Slime + Claude Code tool contract.

Usage (Linux shell):
    python sweTrain/scripts/convert_qwen3coder_to_claude_code_tools.py \
      /data/swesmith_qwen3coder.jsonl \
      /data/swesmith_qwen3coder_claude_code.jsonl \
      --tools-json /data/claude_code_tools_internal.json \
      --rejects /data/swesmith_claude_code_rejects.jsonl

To replace an existing output or rejects file, add ``--overwrite``. The input
and output paths must be different.

This is a second-stage converter. Its input must be the output of
``convert_swesmith_to_qwen3coder.py``. It rewrites SWE-agent tools to the
schemas passed by Claude Code through Slime's AnthropicAdapter:

* bash -> Bash
* str_replace_editor(view) -> Read
* str_replace_editor(create) -> Write
* str_replace_editor(str_replace) -> Edit (or Write for full-file variants)
* submit -> removed, because Claude Code ends by returning assistant text.

The output is in Slime's internal chat-template representation, rather than
Anthropic's wire representation: tools use ``type/function/parameters`` and
tool results are ``{"role": "tool", "content": ...}``.

Pass ``--tools-json`` when you have captured the complete tool schema from the
Claude Code request received by Slime. The file must contain either that
internal list directly, or an Anthropic ``tools`` list using ``input_schema``.
Without it, the script uses only Bash/Read/Write/Edit, which are the tools
covered by this source dataset.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, deque
from pathlib import Path
from typing import Any


CLAUDE_CODE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "Bash",
            "description": "Execute a bash command in the terminal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The command to execute."},
                    "timeout": {"type": "integer", "description": "Optional timeout in milliseconds."},
                    "description": {"type": "string", "description": "Brief description of the command."},
                    "run_in_background": {"type": "boolean", "description": "Run command in the background."},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "Read",
            "description": "Read a file from the local filesystem.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Absolute path to the file to read."},
                    "offset": {"type": "integer", "description": "Optional first line number to read."},
                    "limit": {"type": "integer", "description": "Optional number of lines to read."},
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "Write",
            "description": "Write complete content to a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Absolute path to the file to write."},
                    "content": {"type": "string", "description": "Complete content to write."},
                },
                "required": ["file_path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "Edit",
            "description": "Replace an exact string in a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Absolute path to the file to modify."},
                    "old_string": {"type": "string", "description": "Text to replace."},
                    "new_string": {"type": "string", "description": "Replacement text."},
                    "replace_all": {"type": "boolean", "description": "Replace every occurrence; defaults to false."},
                },
                "required": ["file_path", "old_string", "new_string"],
            },
        },
    },
]


class ConversionError(ValueError):
    """A source trajectory cannot be mapped without guessing its semantics."""


SUBMIT_ONLY_TEXT_RE = re.compile(
    r"^\s*(?:now\s+)?(?:let(?:'s|\s+us)|i(?:'ll|\s+will))\s+submit(?:\s+(?:again|our solution|the changes))?\s*[:.!]*\s*$",
    re.IGNORECASE,
)


def as_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConversionError(f"{label} must be an object")
    return value


def map_read(path: str, view_range: Any, stats: Counter[str]) -> dict[str, Any]:
    """Map SWE's inclusive view range to Claude Code Read's offset/limit."""
    mapped_args: dict[str, Any] = {"file_path": path}
    if view_range is None:
        return {"type": "function", "function": {"name": "Read", "arguments": mapped_args}}
    if (
        not isinstance(view_range, list)
        or len(view_range) != 2
        or not all(isinstance(value, int) for value in view_range)
        or view_range[0] < 0
        or view_range[1] < view_range[0]
    ):
        raise ConversionError(f"Invalid view_range: {view_range!r}")
    start, end = view_range
    if start == 0:
        # Claude Code is one-indexed. In this malformed SWE variant [0, N]
        # denotes the first N lines, not N + 1 lines.
        mapped_args["offset"] = 1
        mapped_args["limit"] = max(1, end)
        stats["zero_based_view_ranges_normalized"] += 1
    else:
        mapped_args["offset"] = start
        mapped_args["limit"] = end - start + 1
    return {"type": "function", "function": {"name": "Read", "arguments": mapped_args}}


def map_tool_call(call: dict[str, Any], stats: Counter[str]) -> tuple[str, dict[str, Any] | None, str]:
    """Return (source_name, mapped_call, result_handling).

    result_handling is ``tool`` for a retained tool result, ``submit`` for a
    removed submit call, and ``drop`` for an invalid source call and result.
    """
    function = as_dict(call.get("function"), "tool call function")
    source_name = function.get("name")
    arguments = as_dict(function.get("arguments"), f"arguments for {source_name!r}")

    if source_name == "submit":
        if arguments:
            raise ConversionError("submit unexpectedly has arguments")
        return source_name, None, "submit"

    if source_name == "bash":
        command = arguments.get("command")
        if not isinstance(command, str):
            raise ConversionError("bash command must be a string")
        return source_name, {"type": "function", "function": {"name": "Bash", "arguments": {"command": command}}}, "tool"

    if source_name != "str_replace_editor":
        raise ConversionError(f"Unsupported source tool {source_name!r}")

    command = arguments.get("command")
    path = arguments.get("path")
    if not isinstance(path, str):
        raise ConversionError(f"str_replace_editor({command!r}) has no string path")

    if command == "view" or ("view_range" in arguments and "old_str" not in arguments and "file_text" not in arguments):
        if command != "view":
            stats["view_calls_recovered_by_shape"] += 1
        return source_name, map_read(path, arguments.get("view_range"), stats), "tool"

    if command == "create":
        content = arguments.get("file_text")
        if not isinstance(content, str):
            # A create operation without content cannot be represented as Claude
            # Code Write without inventing file contents. Drop it and its result.
            stats["contentless_create_calls_dropped"] += 1
            return source_name, None, "drop"
        return source_name, {
            "type": "function",
            "function": {"name": "Write", "arguments": {"file_path": path, "content": content}},
        }, "tool"

    if command == "str_replace":
        old_string = arguments.get("old_str")
        new_string = arguments.get("new_str")
        file_text = arguments.get("file_text")
        if isinstance(old_string, str) and not isinstance(new_string, str) and isinstance(file_text, str):
            new_string = file_text
            stats["edit_new_string_recovered_from_file_text"] += 1
        if not isinstance(old_string, str) and not isinstance(new_string, str) and isinstance(file_text, str):
            # SWE's editor sometimes labels full-file writes as str_replace.
            stats["full_file_writes_recovered_from_str_replace"] += 1
            return source_name, {
                "type": "function",
                "function": {"name": "Write", "arguments": {"file_path": path, "content": file_text}},
            }, "tool"
        if not isinstance(old_string, str) or not isinstance(new_string, str):
            raise ConversionError("str_replace_editor(str_replace) has no recoverable replacement content")
        return source_name, {
            "type": "function",
            "function": {
                "name": "Edit",
                "arguments": {"file_path": path, "old_string": old_string, "new_string": new_string},
            },
        }, "tool"

    raise ConversionError(f"Unsupported str_replace_editor command {command!r}")


def has_later_assistant(messages: list[dict[str, Any]], start: int) -> bool:
    return any(message.get("role") == "assistant" for message in messages[start + 1 :])


def convert_messages(messages: Any, stats: Counter[str]) -> list[dict[str, Any]]:
    if not isinstance(messages, list):
        raise ConversionError("messages must be a list")
    source_messages = [as_dict(message, "message") for message in messages]
    output: list[dict[str, Any]] = []
    pending: deque[tuple[str, str]] = deque()

    for index, message in enumerate(source_messages):
        role = message.get("role")
        if role in {"system", "user"}:
            content = message.get("content")
            if not isinstance(content, str):
                raise ConversionError(f"{role} content at message {index} must be a string")
            output.append({"role": role, "content": content})
            continue

        if role == "assistant":
            content = message.get("content", "")
            if not isinstance(content, str):
                raise ConversionError(f"assistant content at message {index} must be a string")
            mapped_calls: list[dict[str, Any]] = []
            submit_call_count = 0
            pending.clear()
            for call in message.get("tool_calls") or []:
                source_name, mapped, result_handling = map_tool_call(as_dict(call, "tool call"), stats)
                pending.append((source_name, result_handling))
                if result_handling == "submit":
                    stats["submit_calls_removed"] += 1
                    submit_call_count += 1
                elif result_handling == "tool":
                    assert mapped is not None
                    mapped_calls.append(mapped)
                    stats[f"mapped_to_{mapped['function']['name']}"] += 1
                else:
                    assert result_handling == "drop" and mapped is None
            if submit_call_count and not mapped_calls and not has_later_assistant(source_messages, index):
                if SUBMIT_ONLY_TEXT_RE.fullmatch(content):
                    content = "The task is complete."
                    stats["terminal_submit_text_normalized"] += 1
            assistant: dict[str, Any] = {"role": "assistant", "content": content}
            if mapped_calls:
                assistant["tool_calls"] = mapped_calls
            output.append(assistant)
            continue

        if role == "tool":
            content = message.get("content")
            if not isinstance(content, str):
                raise ConversionError(f"tool content at message {index} must be a string")
            source_name = message.get("name")
            if not pending:
                raise ConversionError(f"Unmatched tool result at message {index}")
            expected_source, result_handling = pending.popleft()
            if source_name and source_name != expected_source:
                raise ConversionError(
                    f"Tool result name {source_name!r} does not match preceding call {expected_source!r}"
                )
            if result_handling == "tool":
                # AnthropicAdapter translates Claude Code tool_result blocks to this exact shape.
                output.append({"role": "tool", "content": content})
                stats["tool_results_kept"] += 1
            elif result_handling == "submit" and has_later_assistant(source_messages, index):
                # An intermediate submit returned reviewer feedback. Preserve the feedback,
                # but as normal user context because Claude Code has no submit tool.
                output.append({"role": "user", "content": content})
                stats["submit_results_to_user"] += 1
            elif result_handling == "submit":
                stats["terminal_submit_results_removed"] += 1
            else:
                assert result_handling == "drop"
                stats["dropped_invalid_call_results"] += 1
            continue

        raise ConversionError(f"Unsupported role {role!r} at message {index}")

    if pending:
        # The expected case is a final submit without a tool result. Non-submit calls
        # with no result would create an invalid interaction and must be rejected.
        unreturned = list(pending)
        if any(result_handling == "tool" for _, result_handling in unreturned):
            raise ConversionError(f"Missing tool result for calls: {unreturned!r}")
        stats["terminal_submit_without_result"] += sum(
            1 for _, result_handling in unreturned if result_handling == "submit"
        )
        stats["invalid_calls_without_result_dropped"] += sum(
            1 for _, result_handling in unreturned if result_handling == "drop"
        )

    if not output or output[0].get("role") != "system":
        raise ConversionError("First output message must be system")
    if not any(message["role"] == "assistant" for message in output):
        raise ConversionError("Trajectory has no assistant messages")
    return output


def convert_record(record: dict[str, Any], stats: Counter[str]) -> dict[str, Any]:
    result: dict[str, Any] = {"messages": convert_messages(record.get("messages"), stats), "tools": CLAUDE_CODE_TOOLS}
    if "instance_id" in record:
        result["instance_id"] = record["instance_id"]
    return result


def load_tools_schema(path: Path | None) -> list[dict[str, Any]]:
    """Load Slime-internal or Anthropic-wire tool definitions from JSON."""
    if path is None:
        return CLAUDE_CODE_TOOLS
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConversionError(f"Cannot load --tools-json {path}: {exc}") from exc
    if isinstance(value, dict):
        value = value.get("tools")
    if not isinstance(value, list):
        raise ConversionError("--tools-json must contain a JSON list or an object with a tools list")

    internal: list[dict[str, Any]] = []
    for index, raw_tool in enumerate(value):
        tool = as_dict(raw_tool, f"tools[{index}]")
        if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
            function = as_dict(tool["function"], f"tools[{index}].function")
            parameters = function.get("parameters")
            if not isinstance(function.get("name"), str) or not isinstance(parameters, dict):
                raise ConversionError(f"Invalid internal tool schema at tools[{index}]")
            internal.append(
                {
                    "type": "function",
                    "function": {
                        "name": function["name"],
                        "description": function.get("description", ""),
                        "parameters": parameters,
                    },
                }
            )
            continue
        # This is exactly AnthropicAdapter._tools_to_chat_tools()'s conversion.
        name = tool.get("name")
        parameters = tool.get("input_schema") or tool.get("parameters")
        if not isinstance(name, str) or not isinstance(parameters, dict):
            raise ConversionError(f"Invalid Anthropic tool schema at tools[{index}]")
        internal.append(
            {
                "type": "function",
                "function": {"name": name, "description": tool.get("description", ""), "parameters": parameters},
            }
        )

    required_names = {"Bash", "Read", "Write", "Edit"}
    present_names = {tool["function"]["name"] for tool in internal}
    missing = required_names - present_names
    if missing:
        raise ConversionError(f"--tools-json is missing required mapped tools: {sorted(missing)}")
    return internal


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_jsonl", type=Path, help="Input from convert_swesmith_to_qwen3coder.py")
    parser.add_argument("output_jsonl", type=Path, help="Output JSONL with Claude Code tools")
    parser.add_argument("--rejects", type=Path, help="Write rejected source rows with error details here")
    parser.add_argument(
        "--tools-json",
        type=Path,
        help="Captured complete Claude Code tool schema, in Anthropic or Slime-internal JSON form",
    )
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing an existing output/rejects file")
    args = parser.parse_args()

    if not args.input_jsonl.is_file():
        parser.error(f"Input file does not exist: {args.input_jsonl}")
    if args.input_jsonl.resolve() == args.output_jsonl.resolve():
        parser.error("Input and output paths must be different")
    for path in (args.output_jsonl, args.rejects):
        if path and path.exists() and not args.overwrite:
            parser.error(f"Refusing to overwrite {path}; pass --overwrite to allow it")
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)

    try:
        output_tools = load_tools_schema(args.tools_json)
    except ConversionError as exc:
        parser.error(str(exc))

    stats: Counter[str] = Counter()
    rejects_handle = args.rejects.open("w", encoding="utf-8") if args.rejects else None
    try:
        with args.input_jsonl.open(encoding="utf-8") as source, args.output_jsonl.open("w", encoding="utf-8") as target:
            for line_number, line in enumerate(source, 1):
                if not line.strip():
                    continue
                stats["input_rows"] += 1
                try:
                    record = as_dict(json.loads(line), "record")
                    converted = convert_record(record, stats)
                    converted["tools"] = output_tools
                except (ConversionError, TypeError, json.JSONDecodeError) as exc:
                    stats["rejected_rows"] += 1
                    if rejects_handle:
                        rejects_handle.write(
                            json.dumps({"line": line_number, "error": str(exc), "source": line.rstrip()}, ensure_ascii=False)
                            + "\n"
                        )
                    continue
                target.write(json.dumps(converted, ensure_ascii=False, separators=(",", ":")) + "\n")
                stats["written_rows"] += 1
    finally:
        if rejects_handle:
            rejects_handle.close()

    summary_keys = (
        "input_rows",
        "written_rows",
        "rejected_rows",
        "mapped_to_Bash",
        "mapped_to_Read",
        "mapped_to_Write",
        "mapped_to_Edit",
        "submit_calls_removed",
        "tool_results_kept",
        "submit_results_to_user",
        "terminal_submit_results_removed",
        "terminal_submit_without_result",
        "terminal_submit_text_normalized",
        "zero_based_view_ranges_normalized",
        "view_calls_recovered_by_shape",
        "edit_new_string_recovered_from_file_text",
        "full_file_writes_recovered_from_str_replace",
        "contentless_create_calls_dropped",
        "dropped_invalid_call_results",
        "invalid_calls_without_result_dropped",
    )
    print(" ".join(f"{key}={stats[key]}" for key in summary_keys))
    if stats["rejected_rows"]:
        print("Rejected rows were skipped; inspect --rejects output before training.", file=sys.stderr)


if __name__ == "__main__":
    main()
