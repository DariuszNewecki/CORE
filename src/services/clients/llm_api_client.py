# src/services/clients/llm_api_client.py
"""
Provides a base client for asynchronous and synchronous communication with
Chat Completions and Embedding APIs for LLM interactions.
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any, List

import httpx
from shared.config import settings
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

        try:
            connect_timeout = int(settings.model_extra.get("LLM_CONNECT_TIMEOUT", 10))
            request_timeout = int(settings.model_extra.get("LLM_REQUEST_TIMEOUT", 180))
        except (ValueError, TypeError):
            connect_timeout = 10
            request_timeout = 180

        self.timeout_config = httpx.Timeout(
            connect=connect_timeout, read=request_timeout, write=30.0, pool=None
        )
        self.async_client = httpx.AsyncClient(timeout=self.timeout_config, http2=True)
        self.sync_client = httpx.Client(timeout=self.timeout_config, http2=True)

    def _determine_api_type(self, base_url: str) -> str:
        """Determines the API type based on the URL."""
        if "anthropic" in base_url:
            return "anthropic"
        if "localhost" in base_url or "127.0.0.1" in base_url or "192.168" in base_url:
            return "ollama_compatible"
        return "openai"

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
            return {"model": self.model_name, "input": [prompt]}
        if self.api_type == "anthropic":
            return {
                "model": self.model_name,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            }
        else:
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
            else:
                return response_data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as e:
            log.error(
                f"Could not parse response for task '{task_type}': {response_data}"
            )
            raise ValueError(f"Invalid API response structure: {e}") from e

    # ID: aded16ca-2a27-4690-a69a-7c5aec0153e9
    async def make_request_async(
        self, prompt: str, user_id: str = "core_system", task_type: str = "chat"
    ) -> Any:
        api_url = self._get_api_url(task_type)
        payload = self._prepare_payload(prompt, user_id, task_type)
        backoff_delays = [1.0, 2.0, 4.0]

        for attempt in range(len(backoff_delays) + 1):
            try:
                response = await self.async_client.post(
                    api_url, headers=self.headers, json=payload
                )
                response.raise_for_status()
                return self._parse_response(response.json(), task_type)
            except Exception as e:
                error_message = f"Request failed (attempt {attempt + 1}/{len(backoff_delays) + 1}) for {api_url}: {type(e).__name__} - {e}"
                if attempt < len(backoff_delays):
                    wait_time = backoff_delays[attempt] + random.uniform(0, 0.5)
                    log.warning(f"{error_message}. Retrying in {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)
                    continue
                log.error(f"Final attempt failed: {error_message}", exc_info=True)
                raise

    # ID: 6f1354ee-09ee-49d1-8eeb-a4fcc7c1bc58
    async def get_embedding(self, text: str) -> List[float]:
        return await self.make_request_async(
            prompt=text, user_id="embedding_service", task_type="embedding"
        )

    # ID: cfe08d4d-f3d5-475f-87ab-849846e97886
    def make_request_sync(
        self, prompt: str, user_id: str = "core_system", task_type: str = "chat"
    ) -> Any:
        api_url = self._get_api_url(task_type)
        payload = self._prepare_payload(prompt, user_id, task_type)
        backoff_delays = [1.0, 2.0, 4.0]

        for attempt in range(len(backoff_delays) + 1):
            try:
                response = self.sync_client.post(
                    api_url, headers=self.headers, json=payload
                )
                response.raise_for_status()
                return self._parse_response(response.json(), task_type)
            except Exception as e:
                # --- THIS IS THE FIX: ADD DETAILED LOGGING ---
                error_message = f"Sync request failed (attempt {attempt + 1}/{len(backoff_delays) + 1}) for {api_url}: {type(e).__name__} - {e}"
                if isinstance(e, httpx.HTTPStatusError):
                    error_message += f"\nResponse body: {e.response.text}"
                # --- END OF FIX ---
                if attempt < len(backoff_delays):
                    wait_time = backoff_delays[attempt] + random.uniform(0, 0.5)
                    log.warning(f"{error_message}. Retrying in {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    continue
                log.error(f"Final sync attempt failed: {error_message}", exc_info=True)
                raise
