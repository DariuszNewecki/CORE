# src/shared/infrastructure/llm/providers/ollama.py

"""
Provides an AIProvider implementation for Ollama APIs.
"""

from __future__ import annotations

from typing import Any

import httpx

from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger

from .base import AIProvider


logger = getLogger(__name__)
GHOST_VECTOR_START = [0.63719, 0.45393, -4.16063]
_DEFAULT_SYSTEM = "You are a helpful assistant."

# nomic-embed-text supports up to 8192 tokens. At ~3 chars/token for source
# code, the configured cap (default 20000) sits safely under the limit for
# the vast majority of files.
_CFG_EMB = load_operational_config().embedding


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
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
        usage_sink: dict[str, int] | None = None,
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
                        When None, falls back to the operational default.
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
        if max_tokens is None:
            max_tokens = load_operational_config().llm.default_max_tokens
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
            if usage_sink is not None:
                if "prompt_eval_count" in data:
                    usage_sink["prompt_tokens"] = int(data["prompt_eval_count"])
                if "eval_count" in data:
                    usage_sink["completion_tokens"] = int(data["eval_count"])
            return data["message"]["content"]

    # ID: fcc3342d-746d-4bb4-b153-8eef9465c0f0
    async def get_embedding(
        self,
        text: str,
        usage_sink: dict[str, int] | None = None,
    ) -> list[float]:
        """
        Generates an embedding using the Ollama /api/embed format (Ollama 0.4+).

        Uses the current Ollama embedding API:
            POST /api/embed
            payload: {"model": ..., "input": ..., "options": {"num_ctx": ...}}
            response: {"embeddings": [[...]]}

        num_ctx is passed explicitly per-request because Ollama ignores
        num_ctx in the Modelfile for embedding models.

        Input is truncated to _CFG_EMB.max_chars before sending as a
        last-resort safety net.

        Raises:
            RuntimeError: If the model returns a Ghost Vector, indicating
                          an Ollama model failure rather than a real embedding.
        """
        endpoint = f"{self.api_url}/api/embed"

        if len(text) > _CFG_EMB.max_chars:
            logger.warning(
                "Embedding input truncated from %d to %d chars (model context limit).",
                len(text),
                _CFG_EMB.max_chars,
            )
            text = text[: _CFG_EMB.max_chars]

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

    # ID: 9e2c4f81-3a6d-4b85-b4f7-c8d3a1e09f72
    async def get_embeddings_batch(
        self,
        texts: list[str],
        usage_sink: dict[str, int] | None = None,
    ) -> list[list[float]]:
        """Generate embeddings for a list of texts in a single round-trip.

        Uses Ollama's `/api/embed` list-input form (Ollama 0.4+):
            payload: {"model": ..., "input": [t1, t2, ...], "options": {...}}
            response: {"embeddings": [[...], [...], ...]} aligned to input order

        Empty input list returns `[]` without an HTTP call. Each text is
        truncated to `_CFG_EMB.max_chars` before sending, matching the
        single-input path. Ghost-vector check applied per-element; one bad
        vector raises and aborts the whole batch (consumer handles the
        retry/skip — same posture as the single-input path).

        Per #461 D2: token usage from the batch response is summed into
        `usage_sink`; per-text attribution is lost.
        """
        if not texts:
            return []

        endpoint = f"{self.api_url}/api/embed"

        prepared: list[str] = []
        for text in texts:
            if len(text) > _CFG_EMB.max_chars:
                logger.warning(
                    "Embedding input truncated from %d to %d chars (model context limit).",
                    len(text),
                    _CFG_EMB.max_chars,
                )
                prepared.append(text[: _CFG_EMB.max_chars])
            else:
                prepared.append(text)

        payload = {
            "model": self.model_name,
            "input": prepared,
            "options": {"num_ctx": 8192},
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, headers=self.headers, json=payload)
            response.raise_for_status()
            data = response.json()
            vectors = data["embeddings"]

            if len(vectors) != len(prepared):
                raise RuntimeError(
                    f"Ollama returned {len(vectors)} embeddings for {len(prepared)} "
                    "inputs — batch response misalignment"
                )

            for i, vec in enumerate(vectors):
                if len(vec) > 3:
                    is_ghost = all(
                        abs(a - b) < 0.001 for a, b in zip(vec[:3], GHOST_VECTOR_START)
                    )
                    if is_ghost:
                        logger.error(
                            "Ollama returned Ghost Vector (Model Failure) for batch "
                            "input %d/%d (length %s)",
                            i,
                            len(prepared),
                            len(prepared[i]),
                        )
                        raise RuntimeError(
                            "Embedding model failed (Ghost Vector returned in batch)"
                        )

            if usage_sink is not None and "prompt_eval_count" in data:
                usage_sink["prompt_tokens"] = int(data["prompt_eval_count"])

            return vectors
