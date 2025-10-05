# src/services/llm/client.py
"""
A simplified LLM Client that acts as a facade over a specific AI provider.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any, List

from shared.logger import getLogger

from .providers.base import AIProvider

log = getLogger(__name__)


# ID: 8a9f272d-4f69-48f0-bda3-b485446bfc37
class LLMClient:
    """A client that uses a provider strategy to interact with an LLM API."""

    def __init__(self, provider: AIProvider):
        self.provider = provider
        # The model name is now accessed from the provider
        self.model_name = provider.model_name

    async def _request_with_retry(self, method, *args, **kwargs) -> Any:
        """Generic retry logic for any provider method."""
        backoff_delays = [1.0, 2.0, 4.0]
        for attempt in range(len(backoff_delays) + 1):
            try:
                return await method(*args, **kwargs)
            except Exception as e:
                error_message = f"Request failed (attempt {attempt + 1}/{len(backoff_delays) + 1}): {type(e).__name__} - {e}"
                if attempt < len(backoff_delays):
                    wait_time = backoff_delays[attempt] + random.uniform(0, 0.5)
                    log.warning(f"{error_message}. Retrying in {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)
                    continue
                log.error(f"Final attempt failed: {error_message}", exc_info=True)
                raise

    # ID: 1c0b0c26-46a8-4559-9b73-0b8a429a1303
    async def make_request_async(
        self, prompt: str, user_id: str = "core_system"
    ) -> str:
        """Makes a chat completion request using the configured provider with retries."""
        return await self._request_with_retry(
            self.provider.chat_completion, prompt, user_id
        )

    # ID: 262ea6eb-241e-444d-8388-aab25b9b5fa8
    async def get_embedding(self, text: str) -> List[float]:
        """Gets an embedding using the configured provider with retries."""
        return await self._request_with_retry(self.provider.get_embedding, text)
