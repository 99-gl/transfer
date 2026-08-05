"""Protocol normalization and response rendering.

Both supported wire protocols are reduced to ``NormalizedRequest`` before the
service talks to SGLang. This module contains no network or persistence code.
"""

from __future__ import annotations

import hashlib
import copy
import json
import secrets
import time
from typing import Any

from aiohttp import web

from .models import Generation, NormalizedRequest, ParsedOutput, Protocol


def normalize_openai(request: web.Request, body: dict[str, Any]) -> NormalizedRequest:
    return _normalized_request(
        protocol="openai",
        identity=_openai_identity(request, body),
        body=body,
        messages=_openai_messages(body.get("messages")),
        tools=_openai_tools(body.get("tools")),
        max_token_keys=("max_completion_tokens", "max_tokens", "max_output_tokens"),
        stop_keys=("stop",),
        stream=body.get("stream") is True or "text/event-stream" in request.headers.get("Accept", ""),
    )


def normalize_anthropic(request: web.Request, body: dict[str, Any]) -> NormalizedRequest:
    prepared = copy.deepcopy(body)
    _fold_mid_list_system(prepared)
    return _normalized_request(
        protocol="anthropic",
        identity=_anthropic_identity(request),
        body=body,
        messages=_anthropic_messages(prepared.get("messages"), prepared.get("system")),
        tools=_anthropic_tools(prepared.get("tools")),
        max_token_keys=("max_tokens",),
        stop_keys=("stop_sequences",),
        stream=body.get("stream") is True or "text/event-stream" in request.headers.get("Accept", ""),
    )


def openai_response(spec: NormalizedRequest, generation: Generation, parsed: ParsedOutput) -> dict[str, Any]:
    tool_calls = _openai_tool_calls(parsed)
    finish_reason = "tool_calls" if tool_calls else ("length" if generation.finish_reason == "length" else "stop")
    message: dict[str, Any] = {"role": "assistant", "content": None if tool_calls else (parsed.text or None)}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "id": f"chatcmpl_{secrets.token_hex(12)}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": spec.model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": {
            "prompt_tokens": len(generation.prompt_token_ids),
            "completion_tokens": len(generation.output_token_ids),
            "total_tokens": len(generation.prompt_token_ids) + len(generation.output_token_ids),
        },
    }


async def openai_stream(request: web.Request, response: dict[str, Any]) -> web.StreamResponse:
    choice = response["choices"][0]
    message = choice["message"]
    delta: dict[str, Any] = {"role": "assistant"}
    if message.get("content"):
        delta["content"] = message["content"]
    if message.get("tool_calls"):
        delta["tool_calls"] = [{**call, "index": index} for index, call in enumerate(message["tool_calls"])]
    chunk = {
        "id": response["id"],
        "object": "chat.completion.chunk",
        "created": response["created"],
        "model": response["model"],
        "choices": [{"index": 0, "delta": delta, "finish_reason": choice["finish_reason"]}],
    }
    stream = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache"})
    await stream.prepare(request)
    await stream.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\ndata: [DONE]\n\n".encode())
    return stream


def anthropic_response(spec: NormalizedRequest, generation: Generation, parsed: ParsedOutput) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = []
    if parsed.reasoning:
        blocks.append({"type": "thinking", "thinking": parsed.reasoning})
    if parsed.text:
        blocks.append({"type": "text", "text": parsed.text})
    blocks.extend(
        {"type": "tool_use", "id": f"toolu_{secrets.token_hex(8)}", "name": call["name"], "input": call["input"]}
        for call in parsed.tool_uses
    )
    if not blocks:
        blocks.append({"type": "text", "text": ""})
    return {
        "id": f"msg_{secrets.token_hex(12)}",
        "type": "message",
        "role": "assistant",
        "model": spec.model,
        "content": blocks,
        "stop_reason": "tool_use" if parsed.tool_uses else ("max_tokens" if generation.finish_reason == "length" else "end_turn"),
        "stop_sequence": None,
        "usage": {"input_tokens": len(generation.prompt_token_ids), "output_tokens": len(generation.output_token_ids)},
    }


async def anthropic_stream(request: web.Request, response: dict[str, Any]) -> web.StreamResponse:
    stream = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache"})
    await stream.prepare(request)
    start = {
        "type": "message_start",
        "message": {
            "id": response["id"],
            "type": "message",
            "role": "assistant",
            "model": response["model"],
            "content": [],
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": response["usage"]["input_tokens"], "output_tokens": 0},
        },
    }
    await _anthropic_event(stream, "message_start", start)
    for index, block in enumerate(response["content"]):
        block_type = block["type"]
        if block_type == "thinking":
            content_block = {"type": "thinking", "thinking": ""}
            delta = {"type": "thinking_delta", "thinking": block["thinking"]}
        elif block_type == "text":
            content_block = {"type": "text", "text": ""}
            delta = {"type": "text_delta", "text": block["text"]}
        else:
            content_block = {"type": "tool_use", "id": block["id"], "name": block["name"], "input": {}}
            delta = {"type": "input_json_delta", "partial_json": json.dumps(block["input"], ensure_ascii=False)}
        await _anthropic_event(stream, "content_block_start", {"type": "content_block_start", "index": index, "content_block": content_block})
        await _anthropic_event(stream, "content_block_delta", {"type": "content_block_delta", "index": index, "delta": delta})
        await _anthropic_event(stream, "content_block_stop", {"type": "content_block_stop", "index": index})
    await _anthropic_event(
        stream,
        "message_delta",
        {"type": "message_delta", "delta": {"stop_reason": response["stop_reason"], "stop_sequence": None}, "usage": response["usage"]},
    )
    await _anthropic_event(stream, "message_stop", {"type": "message_stop"})
    return stream


async def _anthropic_event(stream: web.StreamResponse, event: str, payload: dict[str, Any]) -> None:
    await stream.write(f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode())


def _normalized_request(
    *,
    protocol: Protocol,
    identity: str,
    body: dict[str, Any],
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    max_token_keys: tuple[str, ...],
    stop_keys: tuple[str, ...],
    stream: bool,
) -> NormalizedRequest:
    return NormalizedRequest(
        protocol=protocol,
        trajectory_id=_trajectory_id(identity),
        model=str(body.get("model") or "adapter-model"),
        request=body,
        messages=messages,
        tools=tools,
        sampling_params=_sampling_params(body, max_token_keys, stop_keys),
        stream=stream,
    )


def _trajectory_id(identity: str) -> str:
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _bearer_token(request: web.Request) -> str | None:
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


def _openai_identity(request: web.Request, body: dict[str, Any]) -> str:
    metadata = body.get("metadata")
    return _bearer_token(request) or (
        str(metadata["session_id"]) if isinstance(metadata, dict) and metadata.get("session_id") else str(body.get("user") or "default")
    )


def _anthropic_identity(request: web.Request) -> str:
    return _bearer_token(request) or request.headers.get("X-Api-Key", "").strip() or "default"


def _sampling_params(body: dict[str, Any], max_token_keys: tuple[str, ...], stop_keys: tuple[str, ...]) -> dict[str, Any]:
    params: dict[str, Any] = {
        "skip_special_tokens": False,
        "spaces_between_special_tokens": False,
        "no_stop_trim": True,
        "max_new_tokens": 4096,
    }
    for key in max_token_keys:
        if body.get(key) is not None:
            params["max_new_tokens"] = int(body[key])
            break
    for key in ("temperature", "top_p", "top_k"):
        if key in body:
            params[key] = body[key]
    for key in stop_keys:
        if body.get(key):
            params["stop"] = body[key]
            break
    return params


def _content_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(filter(None, (_content_text(item) for item in content)))
    if not isinstance(content, dict):
        return str(content)
    block_type = content.get("type")
    if block_type in {"text", "input_text", "output_text"}:
        return str(content.get("text", ""))
    if block_type == "tool_result":
        return _content_text(content.get("content"))
    if block_type in {"image", "image_url", "input_image"}:
        return "[image omitted]"
    if "content" in content:
        return _content_text(content["content"])
    return str(content.get("text", ""))


def _openai_messages(messages: Any) -> list[dict[str, Any]]:
    if not isinstance(messages, list):
        raise web.HTTPBadRequest(text="messages must be a list")
    normalized: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = "system" if message.get("role") == "developer" else message.get("role")
        if role in {"system", "user", "tool"}:
            normalized.append({"role": role, "content": _content_text(message.get("content"))})
        elif role == "assistant":
            assistant: dict[str, Any] = {"role": "assistant", "content": _content_text(message.get("content"))}
            tool_calls = [_openai_tool_call(item) for item in message.get("tool_calls") or []]
            if tool_calls := [item for item in tool_calls if item is not None]:
                assistant["tool_calls"] = tool_calls
            normalized.append(assistant)
    return normalized


def _openai_tool_call(call: Any) -> dict[str, Any] | None:
    function = call.get("function") if isinstance(call, dict) else None
    if not isinstance(function, dict) or not function.get("name"):
        return None
    arguments = function.get("arguments", {})
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {"_raw_arguments": arguments}
    return _canonical_tool_call(str(function["name"]), arguments)


def _anthropic_messages(messages: Any, system: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if system:
        normalized.append({"role": "system", "content": _content_text(system)})
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        blocks = content if isinstance(content, list) else [content]
        if message.get("role") == "user":
            for block in blocks:
                role = "tool" if isinstance(block, dict) and block.get("type") == "tool_result" else "user"
                normalized.append({"role": role, "content": _content_text(block)})
        elif message.get("role") == "assistant":
            assistant: dict[str, Any] = {"role": "assistant", "content": ""}
            texts, thoughts, tool_calls = [], [], []
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    texts.append(str(block.get("text", "")))
                elif block.get("type") == "thinking":
                    thoughts.append(str(block.get("thinking", "")))
                elif block.get("type") == "tool_use":
                    tool_calls.append(_canonical_tool_call(str(block.get("name") or "tool"), block.get("input")))
            assistant["content"] = "".join(texts)
            if thoughts:
                assistant["reasoning_content"] = "".join(thoughts)
            if tool_calls:
                assistant["tool_calls"] = tool_calls
            normalized.append(assistant)
    return normalized


_MID_SYSTEM_PREFIX = "<system-reminder>\n"
_MID_SYSTEM_SUFFIX = "\n</system-reminder>\n"


def _fold_mid_list_system(body: dict[str, Any]) -> None:
    """Move non-leading system messages into adjacent user content.

    Claude Code can insert system reminders in the middle of a conversation,
    while many model chat templates only accept a leading system message.
    """
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        return
    system_indexes = [
        index for index, message in enumerate(messages)
        if isinstance(message, dict) and message.get("role") == "system" and index > 0
    ]
    if not system_indexes:
        return

    def as_blocks(message: dict[str, Any]) -> list[dict[str, Any]]:
        content = message.get("content")
        if isinstance(content, list):
            return content
        message["content"] = [{"type": "text", "text": content if isinstance(content, str) else ""}]
        return message["content"]

    tombstone = object()
    for index in system_indexes:
        system_message = messages[index]
        reminder = {"type": "text", "text": _MID_SYSTEM_PREFIX + _content_text(system_message.get("content")) + _MID_SYSTEM_SUFFIX}
        target = None
        for candidate_index in range(index - 1, -1, -1):
            if isinstance(messages[candidate_index], dict) and messages[candidate_index].get("role") == "user":
                target = messages[candidate_index]
                as_blocks(target).append(reminder)
                break
        if target is None:
            for candidate_index in range(index + 1, len(messages)):
                if isinstance(messages[candidate_index], dict) and messages[candidate_index].get("role") == "user":
                    target = messages[candidate_index]
                    as_blocks(target).insert(0, reminder)
                    break
        if target is None:
            messages[index] = {"role": "user", "content": [reminder]}
        else:
            messages[index] = tombstone
    body["messages"] = [message for message in messages if message is not tombstone]


def _canonical_tool_call(name: str, arguments: Any) -> dict[str, Any]:
    return {"type": "function", "function": {"name": name, "arguments": arguments if isinstance(arguments, dict) else {}}}


def _openai_tools(tools: Any) -> list[dict[str, Any]] | None:
    normalized = []
    for tool in tools or []:
        if not isinstance(tool, dict) or tool.get("type", "function") != "function":
            continue
        function = tool.get("function") if isinstance(tool.get("function"), dict) else tool
        if function.get("name"):
            normalized.append(_chat_tool(function))
    return normalized or None


def _anthropic_tools(tools: Any) -> list[dict[str, Any]] | None:
    return [_chat_tool(tool, parameters_key="input_schema") for tool in tools or [] if isinstance(tool, dict) and tool.get("name")] or None


def _chat_tool(function: dict[str, Any], parameters_key: str = "parameters") -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": function["name"],
            "description": function.get("description", ""),
            "parameters": function.get(parameters_key) or function.get("parameters") or {"type": "object", "properties": {}},
        },
    }


def _openai_tool_calls(parsed: ParsedOutput) -> list[dict[str, Any]]:
    return [
        {
            "id": f"call_{secrets.token_hex(12)}",
            "type": "function",
            "function": {"name": call["name"], "arguments": json.dumps(call["input"], ensure_ascii=False)},
        }
        for call in parsed.tool_uses
    ]
