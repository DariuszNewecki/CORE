# src/shared/infrastructure/llm/providers/openai.py

"""
Provides an AIProvider implementation for OpenAI-compatible APIs (e.g., DeepSeek).
"""

from __future__ import annotations

from typing import Any

import httpx

from shared.logger import getLogger

from .base import AIProvider


logger = getLogger(__name__)
_DEFAULT_SYSTEM = "You are a helpful assistant."


# ID: d73fe343-cad0-459e-9850-a9365a2be942
class OpenAIProvider(AIProvider):
    """Provider for OpenAI-compatible chat and embedding APIs."""

    def _prepare_headers(self) -> dict[str, str]:
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
        response_format: dict[str, Any] | None = None,
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
            response_format: Optional provider-agnostic structured-output contract.

                Supported input shapes from upper layers:
                    {"type": "json_object"}
                    {"type": "json_schema", "schema": {...}}

                Behaviour:
                    - json_object is forwarded as-is to OpenAI-compatible APIs
                      that support chat/completions response_format.
                    - json_schema is forwarded in a conservative compatible shape.
                    - unsupported or malformed values are ignored.
        """
        endpoint = f"{self.api_url}/chat/completions"
        effective_system = (
            system_prompt.strip() if system_prompt.strip() else _DEFAULT_SYSTEM
        )

        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": effective_system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "user": user_id,
        }

        openai_response_format = self._map_response_format(response_format)
        if openai_response_format is not None:
            payload["response_format"] = openai_response_format
            logger.debug(
                "OpenAIProvider forwarding structured output request type '%s' for model '%s'.",
                openai_response_format.get("type"),
                self.model_name,
            )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, headers=self.headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    @staticmethod
    def _map_response_format(
        response_format: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """
        Map provider-agnostic response_format into an OpenAI-compatible payload shape.

        Notes:
            - Many OpenAI-compatible APIs support:
                  {"type": "json_object"}
            - Native JSON Schema support across compatible providers is inconsistent.
              We therefore use a conservative mapping:
                  {"type": "json_schema", "json_schema": {...}}
            - If the upstream endpoint rejects this field, retry logic in LLMClient
              will surface the provider incompatibility clearly.
        """
        if not response_format:
            return None

        format_type = response_format.get("type")

        if format_type == "json_object":
            return {"type": "json_object"}

        if format_type == "json_schema":
            schema = response_format.get("schema")
            if isinstance(schema, dict) and schema:
                return {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "structured_output",
                        "schema": schema,
                    },
                }

            logger.warning(
                "OpenAIProvider received invalid json_schema response_format; ignoring it."
            )
            return None

        logger.warning(
            "OpenAIProvider received unsupported response_format type '%s'; ignoring it.",
            format_type,
        )
        return None

    # ID: bd55279d-308d-4483-890f-05835055b54e
    async def get_embedding(self, text: str) -> list[float]:
        """Generates an embedding using the OpenAI embeddings format."""
        endpoint = f"{self.api_url}/embeddings"
        payload = {"model": self.model_name, "input": [text]}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, headers=self.headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
