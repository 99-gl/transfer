"""Convert SWE-Smith trajectories to Qwen3-Coder multi-turn SFT JSONL.

The input may contain either of the SWE-Smith message encodings:
* legacy: ``messages`` is a JSON string; assistant tool calls are XML and tool
  results are represented by the following user ``OBSERVATION`` message;
* structured: messages use ``role: tool`` and ``assistant.tool_calls``, but
  function arguments may still be JSON strings.

The output uses the Qwen3-Coder tokenizer's native structure.  Do not manually
add ``<tool_call>`` or ``<tool_response>`` tags to the resulting content.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


SYSTEM_PROMPT = """You are a coding agent that can interact with a computer to solve software engineering tasks.
Verify the filesystem location of user-provided paths when their location is ambiguous. Follow the user's requirements, use the available tools when needed, and verify your changes."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Execute a bash command in the terminal.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string", "description": "Command to execute."}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "str_replace_editor",
            "description": "View, create, or edit files in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "enum": ["view", "create", "str_replace", "insert", "undo_edit"],
                    },
                    "path": {"type": "string"},
                    "file_text": {"type": "string"},
                    "old_str": {"type": "string"},
                    "new_str": {"type": "string"},
                    "insert_line": {"type": "integer"},
                    "view_range": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["command", "path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit",
            "description": "Finish the interaction when the task is complete or cannot proceed.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

TOOL_NAMES = {tool["function"]["name"] for tool in TOOLS}
FUNCTION_RE = re.compile(r"<function=([^>\s]+)>(.*?)</function>", re.DOTALL)
PARAMETER_RE = re.compile(r"<parameter=([^>]+)>(.*?)</parameter>", re.DOTALL)


class ConversionError(ValueError):
    """A source trajectory cannot be converted without changing its meaning."""


def message_text(content: Any) -> str:
    """Normalize Anthropic-style content blocks and ordinary text to one string."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            else:
                raise ConversionError(f"Unsupported content block: {block!r}")
        return "\n".join(parts)
    raise ConversionError(f"Unsupported content type: {type(content).__name__}")


def strip_observation_prefix(text: str) -> str:
    return re.sub(r"^OBSERVATION:\s*", "", text, count=1)


def parse_xml_arguments(function_name: str, body: str) -> dict[str, Any]:
    arguments: dict[str, Any] = {}
    for match in PARAMETER_RE.finditer(body):
        name = match.group(1).strip()
        value = match.group(2).strip("\r\n")
        if function_name == "str_replace_editor" and name == "insert_line":
            try:
                arguments[name] = int(value)
                continue
            except ValueError:
                pass
        if function_name == "str_replace_editor" and name == "view_range":
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list) and all(isinstance(item, int) for item in parsed):
                    arguments[name] = parsed
                    continue
            except json.JSONDecodeError:
                pass
        arguments[name] = value
    return arguments


def parse_xml_tool_calls(content: str, assistant_index: int) -> tuple[str, list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []
    for call_index, match in enumerate(FUNCTION_RE.finditer(content)):
        name = match.group(1).strip()
        if name not in TOOL_NAMES:
            raise ConversionError(f"Unknown XML tool {name!r}")
        calls.append(
            {
                "id": f"legacy_call_{assistant_index}_{call_index}",
                "type": "function",
                "function": {"name": name, "arguments": parse_xml_arguments(name, match.group(2))},
            }
        )
    visible_content = FUNCTION_RE.sub("", content).strip()
    return visible_content, calls


def normalize_structured_tool_calls(raw_calls: Any, assistant_index: int) -> list[dict[str, Any]]:
    if raw_calls is None:
        return []
    if isinstance(raw_calls, dict):
        raw_calls = [raw_calls]
    if not isinstance(raw_calls, list):
        raise ConversionError(f"tool_calls must be a list or object, got {type(raw_calls).__name__}")

    calls: list[dict[str, Any]] = []
    for call_index, raw_call in enumerate(raw_calls):
        if not isinstance(raw_call, dict):
            raise ConversionError(f"Invalid tool call: {raw_call!r}")
        function = raw_call.get("function", raw_call)
        if not isinstance(function, dict):
            raise ConversionError(f"Invalid function in tool call: {raw_call!r}")
        name = function.get("name")
        if name not in TOOL_NAMES:
            raise ConversionError(f"Unknown structured tool {name!r}")
        arguments = function.get("arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as exc:
                raise ConversionError(f"Invalid JSON arguments for {name!r}: {arguments!r}") from exc
        if not isinstance(arguments, dict):
            raise ConversionError(f"Arguments for {name!r} must be an object")
        calls.append(
            {
                "id": raw_call.get("id", f"structured_call_{assistant_index}_{call_index}"),
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        )
    return calls


def normalize_messages(raw_messages: Any, stats: Counter[str]) -> list[dict[str, Any]]:
    if isinstance(raw_messages, str):
        try:
            raw_messages = json.loads(raw_messages)
        except json.JSONDecodeError as exc:
            raise ConversionError("messages is not valid JSON") from exc
        stats["messages_json_string"] += 1
    if not isinstance(raw_messages, list):
        raise ConversionError(f"messages must be a list, got {type(raw_messages).__name__}")

    output: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    pending_legacy_calls: list[dict[str, Any]] = []
    for source_index, message in enumerate(raw_messages):
        if not isinstance(message, dict):
            raise ConversionError(f"Message {source_index} is not an object")
        role = message.get("role")
        if role == "system":
            stats["system_replaced"] += 1
            continue

        if role == "assistant":
            content = message_text(message.get("content"))
            structured_calls = normalize_structured_tool_calls(message.get("tool_calls"), source_index)
            if structured_calls:
                calls = structured_calls
                stats["structured_tool_calls"] += len(calls)
            else:
                content, calls = parse_xml_tool_calls(content, source_index)
                stats["xml_tool_calls"] += len(calls)
            assistant: dict[str, Any] = {"role": "assistant", "content": content}
            if calls:
                assistant["tool_calls"] = calls
                pending_legacy_calls = calls.copy()
            else:
                pending_legacy_calls = []
            output.append(assistant)
            continue

        if role == "tool":
            content = strip_observation_prefix(message_text(message.get("content")))
            tool_ids = message.get("tool_call_ids") or []
            if isinstance(tool_ids, str):
                tool_ids = [tool_ids]
            call_id = tool_ids[0] if tool_ids else None
            tool_name = message.get("name")
            if not tool_name and call_id:
                tool_name = next((call["function"]["name"] for call in pending_legacy_calls if call["id"] == call_id), None)
            if not tool_name and pending_legacy_calls:
                tool_name = pending_legacy_calls.pop(0)["function"]["name"]
            if not tool_name:
                raise ConversionError(f"Tool result at message {source_index} has no matching tool name")
            output.append({"role": "tool", "name": tool_name, "content": content})
            stats["structured_tool_messages"] += 1
            continue

        if role == "user":
            content = message_text(message.get("content"))
            if pending_legacy_calls:
                call = pending_legacy_calls.pop(0)
                output.append(
                    {
                        "role": "tool",
                        "name": call["function"]["name"],
                        "content": strip_observation_prefix(content),
                    }
                )
                stats["legacy_observations_to_tool"] += 1
            else:
                output.append({"role": "user", "content": content})
            continue

        raise ConversionError(f"Unsupported role {role!r} at message {source_index}")

    if len(output) < 3 or not any(message["role"] == "assistant" for message in output):
        raise ConversionError("Trajectory has no assistant supervision")
    return output


def convert_record(record: dict[str, Any], stats: Counter[str]) -> dict[str, Any]:
    messages = normalize_messages(record.get("messages"), stats)
    result: dict[str, Any] = {"messages": messages, "tools": TOOLS}
    if "instance_id" in record:
        result["instance_id"] = record["instance_id"]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_jsonl", type=Path, help="Source SWE-Smith JSONL file")
    parser.add_argument("output_jsonl", type=Path, help="Converted Qwen3-Coder JSONL file")
    parser.add_argument("--rejects", type=Path, help="Write rejected source rows with error details here")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing an existing output file")
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

    stats: Counter[str] = Counter()
    rejects_handle = args.rejects.open("w", encoding="utf-8") if args.rejects else None
    try:
        with args.input_jsonl.open(encoding="utf-8") as source, args.output_jsonl.open("w", encoding="utf-8") as target:
            for line_number, line in enumerate(source, 1):
                if not line.strip():
                    continue
                stats["input_rows"] += 1
                try:
                    converted = convert_record(json.loads(line), stats)
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

    print(
        " ".join(
            f"{key}={stats[key]}"
            for key in (
                "input_rows",
                "written_rows",
                "rejected_rows",
                "messages_json_string",
                "system_replaced",
                "structured_tool_calls",
                "xml_tool_calls",
                "structured_tool_messages",
                "legacy_observations_to_tool",
            )
        )
    )
    if stats["rejected_rows"]:
        print("Rejected rows were skipped; inspect --rejects output before training.", file=sys.stderr)


if __name__ == "__main__":
    main()
