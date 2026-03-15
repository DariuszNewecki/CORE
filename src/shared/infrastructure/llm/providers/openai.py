# src/shared/infrastructure/llm/providers/openai.py

"""
Provides an AIProvider implementation for OpenAI-compatible APIs (e.g., DeepSeek).
"""

from __future__ import annotations

import httpx

from .base import AIProvider


_DEFAULT_SYSTEM = "You are a helpful assistant."


# ID: d73fe343-cad0-459e-9850-a9365a2be942
class OpenAIProvider(AIProvider):
    """Provider for OpenAI-compatible chat and embedding APIs."""

    def _prepare_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    # ID: 14948fa2-8ab2-4e16-addf-de5c1d24a807
    async def chat_completion(
        self,
        prompt: str,
        user_id: str,
        system_prompt: str = "",
        max_tokens: int = 4096,
    ) -> str:
        """
        Generates a chat completion using the OpenAI chat/completions format.

        Args:
            prompt: User-turn content.
            user_id: Forwarded as the 'user' field for OpenAI audit tracing.
            system_prompt: Constitutional system prompt sent as the first
                           system-role message. Falls back to a neutral default
                           when empty.
            max_tokens: Maximum tokens to generate, forwarded directly to the API.
        """
        endpoint = f"{self.api_url}/chat/completions"
        effective_system = (
            system_prompt.strip() if system_prompt.strip() else _DEFAULT_SYSTEM
        )
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": effective_system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "user": user_id,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, headers=self.headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    # ID: bd55279d-308d-4483-890f-05835055b54e
    async def get_embedding(self, text: str) -> list[float]:
        """Generates an embedding using the OpenAI embeddings format."""
        endpoint = f"{self.api_url}/v1/embeddings"
        payload = {"model": self.model_name, "input": [text]}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, headers=self.headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
