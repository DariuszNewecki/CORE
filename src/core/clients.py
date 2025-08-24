# src/core/clients.py
"""
Clients for communicating with LLMs in the CORE ecosystem.
This module provides a base client for interacting with Chat Completions APIs.
"""
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

        if not api_url.endswith("/v1/chat/completions"):
            self.api_url = api_url.rstrip("/") + "/v1/chat/completions"
        else:
            self.api_url = api_url

        self.model_name = model_name
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self.async_client = httpx.AsyncClient(timeout=180.0)

    def make_request(self, prompt: str, user_id: str = "core_system") -> str:
        """
        Sends a prompt to the configured Chat Completions API. (Synchronous)
        """
        import requests  # Lazy import for this secondary method

        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "user": user_id,
        }
        try:
            log.debug(
                f"Sending request to {self.api_url} for model {self.model_name}..."
            )
            response = requests.post(
                self.api_url, headers=self.headers, json=payload, timeout=180
            )
            response.raise_for_status()
            response_data = response.json()
            content = response_data["choices"][0]["message"]["content"]
            log.debug("Successfully received and parsed LLM response.")
            return content if content is not None else ""
        except requests.exceptions.RequestException as e:
            log.error(
                f"Network error during LLM request to {self.api_url}: {e}",
                exc_info=True,
            )
            return f"Error: Could not connect to LLM endpoint. Details: {e}"
        except (KeyError, IndexError):
            log.error(
                f"Error parsing LLM response. Full response: {response.text}",
                exc_info=True,
            )
            return "Error: Could not parse response from API."

    async def make_request_async(
        self, prompt: str, user_id: str = "core_system"
    ) -> str:
        """
        Sends a prompt asynchronously to the configured Chat Completions API.
        """
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "user": user_id,
        }
        try:
            log.debug(
                f"Sending async request to {self.api_url} for model {self.model_name}..."
            )
            response = await self.async_client.post(
                self.api_url, headers=self.headers, json=payload
            )
            response.raise_for_status()
            response_data = response.json()
            content = response_data["choices"][0]["message"]["content"]
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
        except (KeyError, IndexError, json.JSONDecodeError):
            log.error(
                f"Error parsing async LLM response. Full response: {response.text}",
                exc_info=True,
            )
            return "Error: Could not parse response from API."