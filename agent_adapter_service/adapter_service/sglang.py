"""Minimal SGLang ``/generate`` client."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import aiohttp

from .models import Generation


class SGLangError(RuntimeError):
    """Raised when SGLang cannot complete a generation request."""


class SGLangClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def generate(
        self,
        *,
        prompt_token_ids: list[int],
        sampling_params: dict[str, Any],
        routing_key: str,
    ) -> Generation:
        request_id = uuid.uuid4().hex
        timeout = aiohttp.ClientTimeout(total=None, sock_read=900)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session, session.post(
                f"{self.base_url}/generate",
                json={
                    "rid": request_id,
                    "input_ids": prompt_token_ids,
                    "sampling_params": sampling_params,
                    "return_logprob": True,
                },
                headers={"X-SMG-Routing-Key": routing_key},
            ) as response:
                if response.status >= 400:
                    raise SGLangError(f"SGLang returned {response.status}: {(await response.text())[:400]}")
                payload = await response.json(content_type=None)
        except asyncio.CancelledError:
            await self._abort(request_id)
            raise
        except aiohttp.ClientError as error:
            raise SGLangError(f"SGLang request failed: {error}") from error

        meta = payload.get("meta_info") or {}
        token_logprobs = meta.get("output_token_logprobs") or []
        return Generation(
            request_id=request_id,
            prompt_token_ids=prompt_token_ids,
            output_token_ids=[item[1] for item in token_logprobs],
            output_logprobs=[float(item[0]) for item in token_logprobs],
            finish_reason=(meta.get("finish_reason") or {}).get("type", "stop") or "stop",
        )

    async def _abort(self, request_id: str) -> None:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                await session.post(f"{self.base_url}/abort_request", json={"rid": request_id})
        except aiohttp.ClientError:
            pass
