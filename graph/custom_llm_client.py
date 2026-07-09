"""
自定义 LLM Client，用于清理推理模型的 <think> 标签
"""
import json
import re
import logging
import typing

import openai
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel

from graphiti_core.llm_client import OpenAIGenericClient
from graphiti_core.llm_client.config import DEFAULT_MAX_TOKENS, ModelSize
from graphiti_core.llm_client.errors import EmptyResponseError, RateLimitError
from graphiti_core.prompts.models import Message

logger = logging.getLogger(__name__)


class ThinkTagCleaningClient(OpenAIGenericClient):
    """
    包装 OpenAIGenericClient，自动清理响应中的 <think>...</think> 标签
    适用于 DeepSeek-R1、QwQ 等推理模型
    """

    @staticmethod
    def _remove_think_tags(text: str) -> str:
        """
        移除 <think>...</think> 标签及其内容
        支持多种格式：<think>、<Think>、<THINK>
        """
        # 移除 <think>...</think> 及其内容（不区分大小写）
        cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.IGNORECASE | re.DOTALL)

        # 移除可能残留的单独标签
        cleaned = re.sub(r'</?think>', '', cleaned, flags=re.IGNORECASE)

        # 清理多余的空白
        cleaned = cleaned.strip()

        return cleaned

    async def _generate_response(
        self,
        messages: list[Message],
        response_model: type[BaseModel] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        model_size: ModelSize = ModelSize.medium,
    ) -> dict[str, typing.Any]:
        """
        重写 _generate_response，在 json.loads 之前清理 think 标签
        """
        openai_messages: list[ChatCompletionMessageParam] = []
        for m in messages:
            m.content = self._clean_input(m.content)
            if m.role == 'user':
                openai_messages.append({'role': 'user', 'content': m.content})
            elif m.role == 'system':
                openai_messages.append({'role': 'system', 'content': m.content})

        try:
            response = await self.client.chat.completions.create(
                model=self.model or 'gpt-4.1-mini',
                messages=openai_messages,
                temperature=self.temperature,
                max_tokens=max_tokens,
                response_format=self._build_response_format(response_model),  # type: ignore[arg-type]
            )
            result = response.choices[0].message.content or ''

            # 检查空响应
            if not result:
                raise EmptyResponseError('LLM returned an empty response')

            # ===== 关键修改：在这里清理 think 标签 =====
            result = self._remove_think_tags(result)
            logger.debug(f"After removing <think> tags, result length: {len(result)}")
            # ==========================================

            # 清理 Markdown 代码块
            result = self._strip_code_fences(result)

            # 解析 JSON
            return json.loads(result)

        except openai.RateLimitError as e:
            raise RateLimitError from e
        except Exception as e:
            logger.error(f'Error in generating LLM response: {e}')
            raise
