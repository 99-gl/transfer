"""Parse one decoded SGLang generation into text, reasoning, and tool calls."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from .models import OutputParserConfig, ParsedOutput

logger = logging.getLogger(__name__)


def parse_model_output(
    raw_output: str,
    tools: list[dict[str, Any]] | None,
    config: OutputParserConfig,
) -> ParsedOutput:
    """Apply the configured SGLang parsers, then use XML as a fallback.

    ``/generate`` returns token IDs and the corresponding decoded text. SGLang's
    server-side parser settings govern streaming/OpenAI endpoints, but this
    adapter calls the low-level endpoint directly, so it must apply the same
    parser names locally before it can form an Anthropic/OpenAI response.
    """
    reasoning, visible_text = _split_reasoning(raw_output, config.reasoning_parser)
    visible_text, tool_uses = _parse_sglang_tool_calls(visible_text, tools, config.tool_call_parser)
    if not tool_uses:
        visible_text, tool_uses = _parse_xml_tool_calls(visible_text, tools)
    return ParsedOutput(reasoning=reasoning, text=visible_text.strip(), tool_uses=tool_uses)


def _split_reasoning(text: str, parser_name: str | None) -> tuple[str, str]:
    if not parser_name:
        return "", text
    try:
        from sglang.srt.parser.reasoning_parser import ReasoningParser

        reasoning, visible_text = ReasoningParser(model_type=parser_name, stream_reasoning=False).parse_non_stream(text)
        reasoning, visible_text = reasoning or "", visible_text or ""
        if not reasoning and "</think>" in visible_text:
            reasoning, visible_text = visible_text.split("</think>", 1)
        return reasoning, visible_text
    except ImportError as error:
        raise RuntimeError("reasoning parser configured but the 'sglang' Python package is not installed") from error
    except Exception:
        logger.exception("reasoning parser %r failed; preserving unparsed output", parser_name)
        return "", text


def _parse_sglang_tool_calls(
    text: str,
    tools: list[dict[str, Any]] | None,
    parser_name: str | None,
) -> tuple[str, list[dict[str, Any]]]:
    if not parser_name or not tools:
        return text, []
    try:
        from sglang.srt.entrypoints.openai.protocol import Function, Tool
        from sglang.srt.function_call.function_call_parser import FunctionCallParser

        parser = FunctionCallParser(
            tools=[Tool(type="function", function=Function(**tool["function"])) for tool in tools],
            tool_call_parser=parser_name,
        )
        if not parser.has_tool_call(text):
            return text, []
        visible_text, calls = parser.parse_non_stream(text)
        tool_uses = []
        for call in calls:
            try:
                arguments = json.loads(call.parameters or "{}")
            except json.JSONDecodeError:
                arguments = {"_raw_arguments": call.parameters}
            tool_uses.append({"name": call.name or "tool", "input": arguments})
        return visible_text or "", tool_uses
    except ImportError as error:
        raise RuntimeError("tool-call parser configured but the 'sglang' Python package is not installed") from error
    except Exception:
        logger.exception("tool-call parser %r failed; trying XML fallback", parser_name)
        return text, []


def _parse_xml_tool_calls(text: str, tools: list[dict[str, Any]] | None) -> tuple[str, list[dict[str, Any]]]:
    valid_names = {tool.get("function", {}).get("name") for tool in tools or []}
    tool_uses: list[dict[str, Any]] = []
    text_parts: list[str] = []
    offset = 0
    for match in re.finditer(r"<tool_call>\s*<function=([^>]+)>(.*?)</function>\s*</tool_call>", text, re.DOTALL):
        name, body = match.group(1), match.group(2)
        if name not in valid_names:
            continue
        text_parts.append(text[offset : match.start()])
        arguments = {
            item.group(1): item.group(2).strip()
            for item in re.finditer(r"<parameter=([^>]+)>(.*?)</parameter>", body, re.DOTALL)
        }
        tool_uses.append({"name": name, "input": arguments})
        offset = match.end()
    text_parts.append(text[offset:])
    return "".join(text_parts), tool_uses
