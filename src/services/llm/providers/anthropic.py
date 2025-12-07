# src/services/llm/providers/anthropic.py
"""
Provides an AIProvider implementation for Anthropic (Claude) APIs.
"""

from __future__ import annotations

import httpx

from shared.logger import getLogger

from .base import AIProvider


logger = getLogger(__name__)


# ID: e9fcc117-b932-4e8b-9310-fcc2827fd890
class AnthropicProvider(AIProvider):
    """Provider for Anthropic's Messages API."""

    def _prepare_headers(self) -> dict:
        if not self.api_key:
            raise ValueError("Anthropic API requires an API key.")

        # FIX: Aggressively strip whitespace from the key
        clean_key = self.api_key.strip()

        return {
            "x-api-key": clean_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    # ID: 1592c054-de5e-4a21-a161-9b01369ef729
    async def chat_completion(self, prompt: str, user_id: str) -> str:
        """Generates a chat completion using the Anthropic Messages API."""
        # Ensure no trailing slashes issues
        base = self.api_url.rstrip("/")
        endpoint = f"{base}/v1/messages"

        payload = {
            "model": self.model_name,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }

        # Detailed logging for debugging (redacting key)
        logger.debug("Anthropic Req: %s | Model: {self.model_name}", endpoint)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, headers=self.headers, json=payload)

            if response.status_code == 401:
                logger.error(
                    f"Anthropic 401. Headers sent: x-api-key=...{self.headers['x-api-key'][-4:]}"
                )

            response.raise_for_status()
            data = response.json()

            return data["content"][0]["text"]

    # ID: e69c61e4-7e34-45a8-8822-de359f3cedc1
    async def get_embedding(self, text: str) -> list[float]:
        raise NotImplementedError(
            "Anthropic does not provide a native embedding endpoint."
        )
