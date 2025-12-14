# src/shared/infrastructure/adapters/embedding_provider.py

"""
EmbeddingService (quality-first, single-file)

This is now a pure, low-level client. It has no knowledge of the constitution
and receives all configuration during initialization.
"""

from __future__ import annotations

import asyncio
import os
import random
from typing import Any
from urllib.parse import urlparse

import requests

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 54ebd35a-46b6-4c6c-b36b-5bfedd866b36
class EmbeddingService:
    """
    Minimal, robust client for OpenAI-compatible or Ollama-compatible embeddings endpoint.
    Keeps the interface tiny and predictable.
    """

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str | None,
        expected_dim: int,
        request_timeout_sec: float = 120.0,
        connect_timeout_sec: float = 10.0,
        max_retries: int = 4,
    ) -> None:
        """Initializes the EmbeddingService with explicit configuration."""
        self.model = model
        self.expected_dim = expected_dim
        self.base_url = base_url
        self.api_key = api_key
        self.request_timeout_sec = request_timeout_sec
        self.connect_timeout_sec = connect_timeout_sec
        self.max_retries = max_retries
        self._validate_configuration()
        self._detect_api_type_and_endpoint()
        self._log_initialization_info()
        if os.getenv("PYTEST_CURRENT_TEST") is None:
            self._check_server_health()

    def _validate_configuration(self) -> None:
        """Validates that required configuration parameters are present."""
        if not self.base_url or not self.model:
            raise ValueError("base_url and model are required for EmbeddingService.")
        parsed_url = urlparse(self.base_url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError(f"Invalid base_url: {self.base_url}")

    def _detect_api_type_and_endpoint(self) -> None:
        """Detects the API type and sets the appropriate endpoint path."""
        parsed_url = urlparse(self.base_url)
        if "11434" in self.base_url or "ollama" in parsed_url.netloc.lower():
            self.api_type = "ollama_compatible"
            self.endpoint_path = "/api/embeddings"
        else:
            self.api_type = "openai"
            self.endpoint_path = "/v1/embeddings"

    def _log_initialization_info(self) -> None:
        """Logs initialization information."""
        logger.info(
            "EmbeddingService: model=%s dim=%s url=%s",
            self.model,
            self.expected_dim,
            self.base_url,
        )

    def _check_server_health(self) -> None:
        """Checks if the embedding server is responsive and model is available."""
        try:
            health_endpoint = self._get_health_check_endpoint()
            response = requests.get(health_endpoint, timeout=self.connect_timeout_sec)
            if response.status_code != 200:
                self._handle_health_check_failure(response)
            if self.api_type == "ollama_compatible":
                self._validate_ollama_model_availability(response)
        except Exception as e:
            logger.error(
                "Failed to check embedding server health: %s", e, exc_info=True
            )
            raise RuntimeError(f"Embedding server health check failed: {e}") from e

    def _get_health_check_endpoint(self) -> str:
        """Returns the appropriate health check endpoint based on API type."""
        if self.api_type == "ollama_compatible":
            return f"{self.base_url}/api/tags"
        else:
            return f"{self.base_url}/v1/models"

    def _handle_health_check_failure(self, response: requests.Response) -> None:
        """Handles failed health check responses."""
        logger.error(
            "Embedding server health check failed: HTTP %s: %s",
            response.status_code,
            response.text[:200],
        )
        raise RuntimeError("Embedding server is not responsive")

    def _validate_ollama_model_availability(self, response: requests.Response) -> None:
        """Validates that the specified model is available on the Ollama server."""
        models = response.json().get("models", [])
        available_model_names = [model.get("name", "") for model in models]
        if self.model not in available_model_names:
            logger.error(
                "Model %s not found on server. Available: %s",
                self.model,
                available_model_names,
            )
            raise RuntimeError(f"Model {self.model} not available on server")

    # ID: 8f14262e-df4b-4db1-9a4a-34d4ade6f8d8
    async def get_embedding(self, text: str) -> list[float]:
        """
        Return a single embedding vector for the given text.
        Raises:
            ValueError if empty input or wrong dimension is returned.
            RuntimeError for non-retryable HTTP failures or server issues.
        """
        text = (text or "").strip()
        if not text:
            raise ValueError("EmbeddingService.get_embedding: empty text")
        payload = self._build_request_payload(text)
        headers = self._build_headers()
        response_data = await self._post_with_retries(json=payload, headers=headers)
        embedding = self._extract_embedding_from_response(response_data)
        self._validate_embedding_dimensions(embedding)
        return embedding

    def _build_request_payload(self, text: str) -> dict[str, str]:
        """Builds the request payload based on API type."""
        if self.api_type == "ollama_compatible":
            return {"model": self.model, "prompt": text}
        else:
            return {"model": self.model, "input": text}

    def _build_headers(self) -> dict[str, str]:
        """Builds request headers, including Authorization if an API key is present."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _extract_embedding_from_response(
        self, response_data: dict[str, Any]
    ) -> list[float]:
        """Extracts the embedding vector from the API response."""
        try:
            embedding = response_data.get("embedding") or response_data.get(
                "data", [{}]
            )[0].get("embedding", [])
        except Exception as e:
            raise RuntimeError(f"EmbeddingService: invalid response format: {e}") from e
        if not isinstance(embedding, list) or not embedding:
            raise RuntimeError("EmbeddingService: empty embedding returned")
        return embedding

    def _validate_embedding_dimensions(self, embedding: list[float]) -> None:
        """Validates that the embedding has the expected dimensions."""
        if len(embedding) != self.expected_dim:
            raise ValueError(
                f"Unexpected embedding dimension {len(embedding)} != expected {self.expected_dim}"
            )

    async def _post_with_retries(
        self, *, json: dict[str, Any], headers: dict[str, str]
    ) -> dict[str, Any]:
        """
        Execute POST in a thread (to keep async),
        with exponential backoff and jitter for transient errors.
        """
        attempt = 0
        last_error: Exception | None = None
        backoff_base_sec = 0.6
        endpoint_url = f"{self.base_url.rstrip('/')}{self.endpoint_path}"
        while attempt <= self.max_retries:
            try:
                response = await self._execute_http_request(endpoint_url, headers, json)
                self._validate_http_response(response)
                return response.json()
            except Exception as e:
                last_error = e
                attempt += 1
                if self._should_stop_retrying(e, attempt):
                    break
                await self._wait_before_retry(
                    attempt, endpoint_url, e, backoff_base_sec
                )
        raise RuntimeError(
            f"EmbeddingService: request to {endpoint_url} failed after {self.max_retries} retries: {last_error}"
        ) from last_error

    async def _execute_http_request(
        self, endpoint_url: str, headers: dict[str, str], json_data: dict[str, Any]
    ) -> requests.Response:
        """Executes the HTTP request in a thread."""
        return await asyncio.to_thread(
            requests.post,
            endpoint_url,
            headers=headers,
            json=json_data,
            timeout=(self.connect_timeout_sec, self.request_timeout_sec),
        )

    def _validate_http_response(self, response: requests.Response) -> None:
        """Validates HTTP response status codes and raises appropriate errors."""
        status_code = response.status_code
        response_text = response.text[:200]
        if status_code in (408, 429, 500, 502, 503, 504):
            raise RuntimeError(f"Transient HTTP {status_code}: {response_text}")
        if status_code == 400:
            raise RuntimeError(f"Bad request: {response_text}")
        if status_code == 401:
            raise RuntimeError(f"Unauthorized: {response_text}")
        if status_code < 200 or status_code >= 300:
            raise RuntimeError(f"HTTP {status_code}: {response_text}")

    def _should_stop_retrying(self, error: Exception, attempt: int) -> bool:
        """Determines whether to stop retrying based on the error and attempt count."""
        if attempt > self.max_retries:
            return True
        if isinstance(error, RuntimeError) and "Transient" not in str(error):
            return True
        return False

    async def _wait_before_retry(
        self, attempt: int, endpoint_url: str, error: Exception, backoff_base_sec: float
    ) -> None:
        """Waits before retrying with exponential backoff and jitter."""
        backoff_time = backoff_base_sec * 2 ** (attempt - 1) + random.uniform(0, 0.1)
        logger.warning(
            "Embedding POST to %s failed (attempt %s/%s): %s; retrying in %.1fs",
            endpoint_url,
            attempt,
            self.max_retries,
            error,
            backoff_time,
        )
        await asyncio.sleep(backoff_time)
