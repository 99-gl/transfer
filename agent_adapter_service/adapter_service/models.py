"""Data contracts shared by the adapter modules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


Protocol = Literal["openai", "anthropic"]


@dataclass(frozen=True)
class NormalizedRequest:
    """A client request expressed in the format needed for one SGLang call."""

    protocol: Protocol
    trajectory_id: str
    model: str
    request: dict[str, Any]
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None
    sampling_params: dict[str, Any]
    stream: bool


@dataclass(frozen=True)
class Generation:
    """The token-level result returned by SGLang for one request."""

    request_id: str
    prompt_token_ids: list[int]
    output_token_ids: list[int]
    output_logprobs: list[float]
    finish_reason: str


@dataclass(frozen=True)
class ParsedOutput:
    """The text and tool calls derived from a decoded model response."""

    reasoning: str
    text: str
    tool_uses: list[dict[str, Any]]


@dataclass(frozen=True)
class OutputParserConfig:
    """SGLang parser names for the single model served by this adapter.

    These names must match the parser settings used when launching that model's
    SGLang server. Either parser is optional because a model may emit only text,
    only tool calls, or neither structured format.
    """

    tool_call_parser: str | None = None
    reasoning_parser: str | None = None
