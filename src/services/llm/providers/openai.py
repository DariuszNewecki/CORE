# src/services/llm/providers/openai.py
"""
Provides an AIProvider implementation for OpenAI-compatible APIs (e.g., DeepSeek).
"""

from __future__ import annotations

import httpx

from .base import AIProvider


# ID: d73fe343-cad0-459e-9850-a9365a2be942
class OpenAIProvider(AIProvider):
    """Provider for OpenAI-compatible chat and embedding APIs."""

    def _prepare_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    # ID: 14948fa2-8ab2-4e16-addf-de5c1d24a807
    async def chat_completion(self, prompt: str, user_id: str) -> str:
        """Generates a chat completion using the OpenAI format."""
        endpoint = f"{self.api_url}/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "user": user_id,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, headers=self.headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    # ID: bd55279d-308d-4483-890f-05835055b54e
    async def get_embedding(self, text: str) -> list[float]:
        """Generates an embedding using the OpenAI format."""
        endpoint = f"{self.api_url}/v1/embeddings"
        payload = {"model": self.model_name, "input": [text]}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, headers=self.headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
