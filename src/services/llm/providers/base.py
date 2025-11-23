# src/services/llm/providers/base.py
"""
Defines the abstract base class for all AI provider strategies.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import httpx


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
        timeout: int = 180,
    ):
        self.api_url = api_url.rstrip("/")
        self.model_name = model_name
        self.api_key = api_key
        self.timeout = httpx.Timeout(timeout)
        self.headers = self._prepare_headers()

    @abstractmethod
    def _prepare_headers(self) -> dict:
        """Prepare the specific headers for this provider."""
        pass

    @abstractmethod
    # ID: af87b72f-3b74-419d-b6c1-635c4185c033
    async def chat_completion(self, prompt: str, user_id: str) -> str:
        """Generate a text completion for a given prompt."""
        pass

    @abstractmethod
    # ID: bf6da823-1185-4a93-98bb-da095eb92f4f
    async def get_embedding(self, text: str) -> list[float]:
        """Generate an embedding vector for a given text."""
        pass
