# src/core/clients.py
"""
Provides a base client for synchronous and asynchronous communication with Chat Completions APIs for LLM interactions.
"""

from __future__ import annotations

import json

import httpx

from shared.logger import getLogger

log = getLogger(__name__)


# CAPABILITY: llm_orchestration
class BaseLLMClient:
    """
    Base class for LLM clients, handling common request logic for Chat APIs.
    Provides shared initialization and error handling for all LLM clients.
    """

    def __init__(self, api_url: str, api_key: str, model_name: str):
        """
        Initialize the LLM client with API credentials and endpoint.
        """
        if not api_url or not api_key:
            raise ValueError(
                f"{self.__class__.__name__} requires both API_URL and API_KEY."
            )

        base_url = api_url.rstrip("/")
        self.model_name = model_name
        self.api_type = "anthropic" if "anthropic" in base_url else "openai"

        if self.api_type == "anthropic":
            log.debug("Anthropic API detected. Setting custom headers.")
            self.api_url = f"{base_url}/v1/messages" # Correctly appends the endpoint
            self.headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
        else:  # OpenAI/DeepSeek compatible
            log.debug("OpenAI/DeepSeek compatible API detected. Setting standard headers.")
            self.api_url = f"{base_url}/v1/chat/completions"
            self.headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

        self.async_client = httpx.AsyncClient(timeout=180.0)

    def _prepare_payload(self, prompt: str, user_id: str) -> dict:
        """Prepares the request payload based on the API type."""
        if self.api_type == "anthropic":
            return {
                "model": self.model_name,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            }
        else:  # openai
            return {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "user": user_id,
            }

    def _parse_response(self, response_data: dict) -> str:
        """Parses the response to extract the content based on API type."""
        try:
            if self.api_type == "anthropic":
                return response_data.get("content", [{}])[0].get("text", "")
            else:  # openai
                return response_data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            log.error(f"Could not parse response structure: {response_data}")
            return "Error: Invalid response structure from API."
            
    # This synchronous version is preserved for compatibility
    def make_request(self, prompt: str, user_id: str = "core_system") -> str:
        """
        Sends a prompt to the configured API. (Synchronous)
        """
        import requests 

        payload = self._prepare_payload(prompt, user_id)
        try:
            log.debug(
                f"Sending sync request to {self.api_url} for model {self.model_name}..."
            )
            response = requests.post(
                self.api_url, headers=self.headers, json=payload, timeout=180
            )
            response.raise_for_status()
            response_data = response.json()
            content = self._parse_response(response_data)
            log.debug("Successfully received and parsed sync LLM response.")
            return content if content is not None else ""
        except requests.exceptions.RequestException as e:
            log.error(
                f"Network error during sync LLM request to {self.api_url}: {e}",
                exc_info=True,
            )
            return f"Error: Could not connect to LLM endpoint. Details: {e}"
        except Exception as e:
            log.error(
                f"Error parsing sync LLM response. Full response: {getattr(response, 'text', str(e))}",
                exc_info=True,
            )
            return "Error: Could not parse response from API."

    async def make_request_async(
        self, prompt: str, user_id: str = "core_system"
    ) -> str:
        """
        Sends a prompt asynchronously to the configured API.
        """
        payload = self._prepare_payload(prompt, user_id)
        try:
            log.debug(
                f"Sending async request to {self.api_url} for model {self.model_name}..."
            )
            response = await self.async_client.post(
                self.api_url, headers=self.headers, json=payload
            )
            response.raise_for_status()
            response_data = response.json()
            content = self._parse_response(response_data)
            log.debug("Successfully received and parsed async LLM response.")
            return content if content is not None else ""
        except httpx.ReadTimeout:
            log.error(f"Network timeout during async LLM request to {self.api_url}.")
            return "Error: Request timed out."
        except httpx.RequestError as e:
            log.error(
                f"Network error during async LLM request to {self.api_url}: {e}",
                exc_info=True,
            )
            return f"Error: Could not connect to LLM endpoint. Details: {e}"
        except Exception as e:
            log.error(
                f"Error parsing async LLM response. Full response: {getattr(response, 'text', str(e))}",
                exc_info=True,
            )
            return "Error: Could not parse response from API."