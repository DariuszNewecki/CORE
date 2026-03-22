# src/shared/infrastructure/llm/providers/ollama.py

"""
Provides an AIProvider implementation for Ollama APIs.
"""

from __future__ import annotations

from typing import Any

import httpx

from shared.logger import getLogger

from .base import AIProvider


logger = getLogger(__name__)
GHOST_VECTOR_START = [0.63719, 0.45393, -4.16063]
_DEFAULT_SYSTEM = "You are a helpful assistant."

# nomic-embed-text supports up to 8192 tokens. At ~3 chars/token for source
# code, 24000 chars sits safely under the limit for the vast majority of files.
_EMBEDDING_MAX_CHARS = 20000


# ID: 3f78f7ca-33b1-4ac3-a701-30885722e7b1
class OllamaProvider(AIProvider):
    """Provider for Ollama-compatible chat and embedding APIs."""

    def _prepare_headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json"}

    # ID: b4ddef76-9da6-4b19-ad12-8f92eac28f86
    async def chat_completion(
        self,
        prompt: str,
        user_id: str,
        system_prompt: str = "",
        max_tokens: int = 4096,
        response_format: dict[str, Any] | None = None,
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
            response_format: Optional provider-agnostic structured-output contract.

                Supported:
                    {"type": "json_object"}
                    {"type": "json_schema", "schema": {...}}

                Ollama mapping:
                    - json_object -> payload["format"] = "json"
                    - json_schema -> payload["format"] = <raw schema dict>

        Returns:
            Raw text content from Ollama's assistant message.
        """
        endpoint = f"{self.api_url}/api/chat"
        effective_system = (
            system_prompt.strip() if system_prompt.strip() else _DEFAULT_SYSTEM
        )

        payload: dict[str, Any] = {
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

        if response_format:
            format_type = response_format.get("type")

            if format_type == "json_schema":
                schema = response_format.get("schema")
                if isinstance(schema, dict) and schema:
                    payload["format"] = schema
                    logger.debug(
                        "OllamaProvider using native JSON Schema structured output "
                        "for model '%s'.",
                        self.model_name,
                    )
                else:
                    logger.warning(
                        "OllamaProvider received invalid json_schema response_format; "
                        "falling back to normal text generation."
                    )
            elif format_type == "json_object":
                payload["format"] = "json"
                logger.debug(
                    "OllamaProvider using JSON object mode for model '%s'.",
                    self.model_name,
                )
            else:
                logger.warning(
                    "OllamaProvider received unsupported response_format type '%s'; "
                    "falling back to normal text generation.",
                    format_type,
                )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, headers=self.headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]

    # ID: fcc3342d-746d-4bb4-b153-8eef9465c0f0
    async def get_embedding(self, text: str) -> list[float]:
        """
        Generates an embedding using the Ollama /api/embed format (Ollama 0.4+).

        Uses the current Ollama embedding API:
            POST /api/embed
            payload: {"model": ..., "input": ..., "options": {"num_ctx": ...}}
            response: {"embeddings": [[...]]}

        num_ctx is passed explicitly per-request because Ollama ignores
        num_ctx in the Modelfile for embedding models.

        Input is truncated to _EMBEDDING_MAX_CHARS before sending as a
        last-resort safety net.

        Raises:
            RuntimeError: If the model returns a Ghost Vector, indicating
                          an Ollama model failure rather than a real embedding.
        """
        endpoint = f"{self.api_url}/api/embed"

        if len(text) > _EMBEDDING_MAX_CHARS:
            logger.warning(
                "Embedding input truncated from %d to %d chars (model context limit).",
                len(text),
                _EMBEDDING_MAX_CHARS,
            )
            text = text[:_EMBEDDING_MAX_CHARS]

        payload = {
            "model": self.model_name,
            "input": text,
            "options": {"num_ctx": 8192},
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, headers=self.headers, json=payload)
            response.raise_for_status()
            data = response.json()
            vec = data["embeddings"][0]

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
