"""
自定义 LLM Client，用于清理推理模型的 <think> 标签
"""
import re
import logging
from typing import Any
from graphiti_core.llm_client import OpenAIGenericClient
from graphiti_core.llm_client.config import LLMConfig, ModelSize
from graphiti_core.prompts.models import Message
from pydantic import BaseModel

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
        max_tokens: int = 16384,
        model_size: ModelSize = ModelSize.medium,
    ) -> dict[str, Any]:
        """
        重写 _generate_response，在解析前清理 think 标签
        """
        # 调用父类方法获取原始响应
        response = await super()._generate_response(
            messages=messages,
            response_model=response_model,
            max_tokens=max_tokens,
            model_size=model_size,
        )

        # 如果响应中包含 content 字段，清理 think 标签
        if isinstance(response, dict):
            # 可能的响应格式
            content = response.get('content') or response.get('text') or response.get('message', {}).get('content')

            if content and isinstance(content, str):
                original_content = content
                cleaned_content = self._remove_think_tags(content)

                if original_content != cleaned_content:
                    logger.debug(f"Removed <think> tags from response. Original length: {len(original_content)}, Cleaned length: {len(cleaned_content)}")

                # 更新响应中的内容
                if 'content' in response:
                    response['content'] = cleaned_content
                elif 'text' in response:
                    response['text'] = cleaned_content
                elif 'message' in response and isinstance(response['message'], dict):
                    response['message']['content'] = cleaned_content

        return response
