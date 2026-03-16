# src/shared/infrastructure/llm/providers/anthropic.py

"""
Provides an AIProvider implementation for the Anthropic Messages API.
Uses httpx directly — no Anthropic SDK dependency required.
"""

from __future__ import annotations

import httpx

from shared.logger import getLogger

from .base import AIProvider


logger = getLogger(__name__)

_DEFAULT_API_URL = "https://api.anthropic.com"
_ANTHROPIC_VERSION = "2023-06-01"
_DEFAULT_SYSTEM = "You are a helpful assistant."


# ID: 3a1b2c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
class AnthropicProvider(AIProvider):
    """Provider for the Anthropic Messages API."""

    def _prepare_headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": _ANTHROPIC_VERSION,
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    # ID: 7b8c9d0e-1f2a-3b4c-5d6e-7f8a9b0c1d2e
    async def chat_completion(
        self,
        prompt: str,
        user_id: str,
        system_prompt: str = "",
        max_tokens: int = 4096,
    ) -> str:
        """
        Generates a chat completion using the Anthropic Messages API.

        Args:
            prompt: User-turn content.
            user_id: Audit identifier (not forwarded — Anthropic API has no user field).
            system_prompt: Constitutional system prompt. Falls back to a neutral
                           default when empty.
            max_tokens: Maximum tokens to generate.
        """
        api_url = self.api_url if self.api_url else _DEFAULT_API_URL
        endpoint = f"{api_url}/v1/messages"
        effective_system = (
            system_prompt.strip() if system_prompt.strip() else _DEFAULT_SYSTEM
        )
        payload = {
            "model": self.model_name,
            "max_tokens": max_tokens,
            "system": effective_system,
            "messages": [
                {"role": "user", "content": prompt},
            ],
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, headers=self.headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]

    # ID: 4e5f6a7b-8c9d-0e1f-2a3b-4c5d6e7f8a9b
    async def get_embedding(self, text: str) -> list[float]:
        """Not supported — Anthropic does not offer an embeddings endpoint."""
        raise NotImplementedError(
            "AnthropicProvider does not support embeddings. "
            "Use OllamaProvider or OpenAIProvider for embedding generation."
        )
