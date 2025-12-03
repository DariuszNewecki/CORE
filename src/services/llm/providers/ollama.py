# src/services/llm/providers/ollama.py
"""
Provides an AIProvider implementation for Ollama APIs.
"""

from __future__ import annotations

import httpx
from shared.logger import getLogger

from .base import AIProvider

logger = getLogger(__name__)

# Known failure mode for nomic-embed-text on Ollama
# If the model fails to process the text (e.g. too long), it may return this static vector.
GHOST_VECTOR_START = [0.63719, 0.45393, -4.16063]


# ID: 4f92f9c9-e264-4e37-afad-2c7ad4e2fbcf
class OllamaProvider(AIProvider):
    """Provider for Ollama-compatible chat and embedding APIs."""

    def _prepare_headers(self) -> dict:
        return {"Content-Type": "application/json"}

    # ID: 2edf6e46-a6e9-4f8f-9f7c-1125df0b47a2
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

    # ID: 679822a7-1d08-42f8-b237-5df7338c3d7f
    async def get_embedding(self, text: str) -> list[float]:
        """Generates an embedding using the Ollama format."""
        endpoint = f"{self.api_url}/api/embeddings"
        payload = {"model": self.model_name, "prompt": text}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, headers=self.headers, json=payload)
            response.raise_for_status()
            data = response.json()
            vec = data["embedding"]

            # Guard against Ghost Vector (Model Failure)
            if len(vec) > 3:
                is_ghost = all(
                    abs(a - b) < 0.001 for a, b in zip(vec[:3], GHOST_VECTOR_START)
                )
                if is_ghost:
                    logger.error(
                        f"Ollama returned Ghost Vector (Model Failure) for input length {len(text)}"
                    )
                    raise RuntimeError("Embedding model failed (Ghost Vector returned)")

            return vec
