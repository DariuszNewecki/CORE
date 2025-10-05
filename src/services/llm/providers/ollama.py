# src/services/llm/providers/ollama.py
"""
Provides an AIProvider implementation for Ollama APIs.
"""

from __future__ import annotations

from typing import List

import httpx

from .base import AIProvider


# ID: 0e708721-68c7-4252-b819-2c1827646b5e
class OllamaProvider(AIProvider):
    """Provider for Ollama-compatible chat and embedding APIs."""

    def _prepare_headers(self) -> dict:
        return {"Content-Type": "application/json"}

    # ID: 434c2772-9daf-4886-9a27-66004814fcff
    async def chat_completion(self, prompt: str, user_id: str) -> str:
        """Generates a chat completion using the Ollama format."""
        # Note: Ollama also supports /v1/chat/completions, but we use the native one for clarity
        endpoint = f"{self.api_url}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,  # Ensure we get a single response
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, headers=self.headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]

    # ID: b74a1365-3b5b-4080-8433-dfe0d4243390
    async def get_embedding(self, text: str) -> List[float]:
        """Generates an embedding using the Ollama format."""
        endpoint = f"{self.api_url}/api/embeddings"
        payload = {"model": self.model_name, "prompt": text}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, headers=self.headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["embedding"]
