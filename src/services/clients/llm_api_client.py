# src/core/clients.py
"""
Provides a base client for asynchronous communication with Chat Completions
and Embedding APIs for LLM interactions.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any, List

import httpx

from shared.logger import getLogger

log = getLogger(__name__)


# ID: ccbed73e-3e71-4ede-ac2a-3069ee9abc0f
class BaseLLMClient:
    """
    Base class for LLM clients, handling common request logic for Chat and Embedding APIs.
    """

    def __init__(self, api_url: str, model_name: str, api_key: str | None = None):
        """Initializes the LLM client with API credentials and endpoint."""
        if not api_url or not model_name:
            raise ValueError(
                f"{self.__class__.__name__} requires both API_URL and MODEL_NAME."
            )

        self.base_url = api_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name
        self.api_type = self._determine_api_type(self.base_url)
        self.headers = self._get_headers()
        self.async_client = httpx.AsyncClient(timeout=180.0)

    def _determine_api_type(self, base_url: str) -> str:
        """Determines the API type based on the URL."""
        if "anthropic" in base_url:
            return "anthropic"
        if "localhost" in base_url or "127.0.0.1" in base_url:
            return "ollama_compatible"
        if "192.168.20.24" in base_url:
            return "ollama_compatible"
        return "openai"  # Default for DeepSeek and OpenAI

    def _get_headers(self) -> dict:
        """Determines the correct headers based on the API type."""
        if self.api_type == "anthropic":
            if not self.api_key:
                raise ValueError("Anthropic API requires an API key.")
            return {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
        elif self.api_type == "openai":
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            return headers
        return {"Content-Type": "application/json"}

    def _get_api_url(self, task_type: str) -> str:
        """Gets the correct API endpoint URL based on the task type."""
        if task_type == "embedding":
            if self.api_type == "ollama_compatible":
                return f"{self.base_url}/api/embeddings"
            return f"{self.base_url}/v1/embeddings"
        if self.api_type == "anthropic":
            return f"{self.base_url}/v1/messages"
        return f"{self.base_url}/v1/chat/completions"

    def _prepare_payload(self, prompt: str, user_id: str, task_type: str) -> dict:
        """Prepares the request payload based on the API and task type."""
        if task_type == "embedding":
            if self.api_type == "ollama_compatible":
                return {"model": self.model_name, "prompt": prompt}
            # OpenAI/DeepSeek use "input"
            return {"model": self.model_name, "input": [prompt]}

        if self.api_type == "anthropic":
            return {
                "model": self.model_name,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            }
        else:  # openai chat
            return {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "user": user_id,
            }

    def _parse_response(self, response_data: dict, task_type: str) -> Any:
        """Parses the response to extract the content based on API and task type."""
        try:
            if task_type == "embedding":
                embedding = response_data.get("embedding") or response_data.get(
                    "data", [{}]
                )[0].get("embedding", [])
                if not embedding:
                    raise ValueError("Invalid embedding format in API response.")
                return embedding

            if self.api_type == "anthropic":
                return response_data.get("content", [{}])[0].get("text", "")
            else:  # openai chat
                return response_data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as e:
            log.error(
                f"Could not parse response for task '{task_type}': {response_data}"
            )
            raise ValueError(f"Invalid API response structure: {e}") from e

    # ID: 966c47f2-fe76-49e3-9691-d541f5c9b802
    async def make_request_async(
        self, prompt: str, user_id: str = "core_system", task_type: str = "chat"
    ) -> Any:
        """Sends a prompt asynchronously to the configured API."""
        api_url = self._get_api_url(task_type)
        payload = self._prepare_payload(prompt, user_id, task_type)

        backoff_delays = [0.8, 1.6, 3.2]
        timeout_config = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=30.0)

        for attempt in range(len(backoff_delays) + 1):
            try:
                response = await self.async_client.post(
                    api_url, headers=self.headers, json=payload, timeout=timeout_config
                )
                response.raise_for_status()
                return self._parse_response(response.json(), task_type)
            except (
                httpx.HTTPStatusError,
                httpx.ReadTimeout,
                httpx.ConnectTimeout,
                httpx.TransportError,
            ) as e:
                if attempt < len(backoff_delays):
                    wait_time = backoff_delays[attempt] + random.uniform(0, 0.5)
                    log.warning(
                        f"Request failed (attempt {attempt + 1}/"
                        f"{len(backoff_delays) + 1}), retrying in "
                        f"{wait_time:.1f}s... Error: {e}"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                log.error(f"Final attempt failed for {api_url}: {e}", exc_info=True)
                raise

    # ID: 08f4f3a4-ac7c-4817-ad31-2d2bc72f0d93
    async def get_embedding(self, text: str) -> List[float]:
        """Convenience method for embedding tasks."""
        return await self.make_request_async(
            prompt=text, user_id="embedding_service", task_type="embedding"
        )
