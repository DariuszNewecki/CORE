# src/shared/infrastructure/llm/providers/anthropic.py

"""
Provides an AIProvider implementation for Anthropic (Claude) APIs.
"""

from __future__ import annotations

import httpx

from shared.logger import getLogger

from .base import AIProvider


logger = getLogger(__name__)


# ID: b170ee96-52c0-4ee4-86fb-19912fe2ab0b
class AnthropicProvider(AIProvider):
    """Provider for Anthropic's Messages API."""

    def _prepare_headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ValueError("Anthropic API requires an API key.")
        clean_key = self.api_key.strip()
        return {
            "x-api-key": clean_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    # ID: 9365b99e-d511-4bd1-8ed7-427083922c63
    async def chat_completion(self, prompt: str, user_id: str) -> str:
        """Generates a chat completion using the Anthropic Messages API."""
        base = self.api_url.rstrip("/")
        endpoint = f"{base}/v1/messages"
        payload = {
            "model": self.model_name,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }

        # Do not log secrets or partial secrets (API key) under any circumstances.
        logger.debug("Anthropic Req: %s | Model: %s", endpoint, self.model_name)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, headers=self.headers, json=payload)

            if response.status_code == 401:
                # Explicitly avoid logging x-api-key (even partially).
                logger.error(
                    "Anthropic request unauthorized (401). Verify API key configuration. "
                    "Endpoint=%s Model=%s",
                    endpoint,
                    self.model_name,
                )

            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]

    # ID: e167c2ab-f8dc-4d67-9177-1ae28ddb3a9a
    async def get_embedding(self, text: str) -> list[float]:
        raise NotImplementedError(
            "Anthropic does not provide a native embedding endpoint."
        )
