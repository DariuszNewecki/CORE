# src/shared/infrastructure/llm/providers/base.py

"""
Defines the abstract base class for all AI provider strategies.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx

from shared.infrastructure.intent.operational_config import load_operational_config


# ID: 32b9740b-010f-4fd0-8886-f17093aa855f
class AIProvider(ABC):
    """
    Abstract base class defining the interface for an AI service provider.
    """

    def __init__(
        self,
        api_url: str,
        model_name: str,
        api_key: str | None = None,
        timeout: int | None = None,
    ):
        if timeout is None:
            timeout = load_operational_config().llm.provider_timeout_sec
        self.api_url = api_url.rstrip("/")
        self.model_name = model_name
        self.api_key = api_key
        self.timeout = httpx.Timeout(timeout)
        self.headers = self._prepare_headers()

    @abstractmethod
    def _prepare_headers(self) -> dict[str, str]:
        """Prepare the specific headers for this provider."""
        pass

    @abstractmethod
    # ID: af87b72f-3b74-419d-b6c1-635c4185c033
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
        Generates a text completion for a given prompt.

        Args:
            prompt: User-turn content.
            user_id: Audit identifier.
            system_prompt: Constitutional system prompt. Empty string uses
                           the provider's built-in default.
            max_tokens: Maximum tokens to generate. Controls response length;
                        passed directly to the underlying API. When None,
                        concrete implementations fall back to the operational
                        default.
            response_format: Optional provider-agnostic structured-output
                             request contract.

                             Supported shapes from upper layers:
                                 {"type": "json_object"}
                                 {"type": "json_schema", "schema": {...}}

                             Providers may:
                                 - support both shapes natively,
                                 - support only one of them,
                                 - ignore unsupported variants and fall back
                                   to normal text generation.
            usage_sink: Optional dict mutated in place after a successful
                        HTTP response to record token usage from the provider
                        envelope. Populated keys: 'prompt_tokens' and
                        'completion_tokens' when the provider exposes them.
                        Allocated per-call by the caller; never shared across
                        concurrent invocations.

        Returns:
            Raw provider response content as a string.
        """
        pass

    @abstractmethod
    # ID: bf6da823-1185-4a93-98bb-da095eb92f4f
    async def get_embedding(
        self,
        text: str,
        usage_sink: dict[str, int] | None = None,
    ) -> list[float]:
        """Generate an embedding vector for a given text.

        Args:
            text: Source text to embed.
            usage_sink: Optional dict mutated in place with 'prompt_tokens'
                        when the provider exposes embedding token counts.
        """
        pass
