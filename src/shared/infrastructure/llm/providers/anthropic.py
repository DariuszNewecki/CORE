# src/shared/infrastructure/llm/providers/anthropic.py

"""
Provides an AIProvider implementation for Ollama APIs.
"""

from __future__ import annotations

import httpx

from shared.logger import getLogger

from .base import AIProvider


logger = getLogger(__name__)
GHOST_VECTOR_START = [0.63719, 0.45393, -4.16063]
_DEFAULT_SYSTEM = "You are a helpful assistant."


# ID: 3f78f7ca-33b1-4ac3-a701-30885722e7b1
class OllamaProvider(AIProvider):
    """Provider for Ollama-compatible chat and embedding APIs."""

    def _prepare_headers(self) -> dict:
        return {"Content-Type": "application/json"}

    # ID: b4ddef76-9da6-4b19-ad12-8f92eac28f86
    async def chat_completion(
        self,
        prompt: str,
        user_id: str,
        system_prompt: str = "",
        max_tokens: int = 4096,
    ) -> str:
        """
        Generates a chat completion using the Ollama /api/chat format.

        Args:
            prompt: User-turn content.
            user_id: Audit identifier (unused by Ollama but kept for interface parity).
            system_prompt: Constitutional system prompt sent as the first
                           system-role message. Falls back to a neutral default
                           when empty so the model always receives a system turn.
            max_tokens: Mapped to Ollama's options.num_predict to cap output length.
        """
        endpoint = f"{self.api_url}/api/chat"
        effective_system = (
            system_prompt.strip() if system_prompt.strip() else _DEFAULT_SYSTEM
        )
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": effective_system},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {
                "num_predict": max_tokens,
            },
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, headers=self.headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]

    # ID: fcc3342d-746d-4bb4-b153-8eef9465c0f0
    async def get_embedding(self, text: str) -> list[float]:
        """
        Generates an embedding using the Ollama /api/embeddings format.

        Raises:
            RuntimeError: If the model returns a Ghost Vector, indicating
                          an Ollama model failure rather than a real embedding.
        """
        endpoint = f"{self.api_url}/api/embeddings"
        payload = {"model": self.model_name, "prompt": text}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, headers=self.headers, json=payload)
            response.raise_for_status()
            data = response.json()
            vec = data["embedding"]
            if len(vec) > 3:
                is_ghost = all(
                    abs(a - b) < 0.001 for a, b in zip(vec[:3], GHOST_VECTOR_START)
                )
                if is_ghost:
                    logger.error(
                        "Ollama returned Ghost Vector (Model Failure) for input length %s",
                        len(text),
                    )
                    raise RuntimeError("Embedding model failed (Ghost Vector returned)")
            return vec
