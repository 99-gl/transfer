"""OpenAI-compatible client adapter for reasoning models that emit think tags."""

from __future__ import annotations

import json
import logging
import re
import typing

import openai
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel

from graphiti_core.llm_client.config import DEFAULT_MAX_TOKENS, ModelSize
from graphiti_core.llm_client.errors import EmptyResponseError, RateLimitError
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.prompts.models import Message

logger = logging.getLogger(__name__)


class ThinkTagCleaningClient(OpenAIGenericClient):
    """Remove reasoning tags before Graphiti parses structured JSON output."""

    @staticmethod
    def _remove_think_tags(text: str) -> str:
        cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r'</?think>', '', cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    async def _generate_response(
        self,
        messages: list[Message],
        response_model: type[BaseModel] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        model_size: ModelSize = ModelSize.medium,
    ) -> dict[str, typing.Any]:
        openai_messages: list[ChatCompletionMessageParam] = []
        for message in messages:
            content = self._clean_input(message.content)
            if message.role in {'user', 'system'}:
                openai_messages.append({'role': message.role, 'content': content})

        try:
            response = await self.client.chat.completions.create(
                model=self.model or 'gpt-4.1-mini',
                messages=openai_messages,
                temperature=self.temperature,
                max_tokens=max_tokens,
                response_format=self._build_response_format(response_model),  # type: ignore[arg-type]
            )
            result = response.choices[0].message.content or ''
            if not result:
                raise EmptyResponseError('LLM returned an empty response')
            result = self._strip_code_fences(self._remove_think_tags(result))
            return json.loads(result)
        except openai.RateLimitError as exc:
            raise RateLimitError from exc
        except Exception:
            logger.exception('Error while generating an LLM response')
            raise
