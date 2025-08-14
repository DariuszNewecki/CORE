# src/core/clients.py
"""
Clients for communicating with the different LLMs in the CORE ecosystem.
This version is updated to use the modern "Chat Completions" API format,
and uses the 'httpx' library for robust, asynchronous network requests.
"""
import json

import httpx
import requests
from shared.config import settings
from shared.logger import getLogger

log = getLogger(__name__)


class BaseLLMClient:
    """
    Base class for LLM clients, handling common request logic for Chat APIs.
    Provides shared initialization and error handling for all LLM clients.
    """

    def __init__(self, api_url: str, api_key: str, model_name: str):
        """
        Initialize the LLM client with API credentials and endpoint.

        Args:
            api_url (str): Base URL for the LLM's chat completions API.
            api_key (str): Authentication token for the API.
            model_name (str): Name of the model to use (e.g., 'gpt-4', 'deepseek-coder').
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
        # --- THIS IS THE UPGRADE (Part 1 of 2) ---
        # We add an async client for concurrent operations, while keeping the sync client for now.
        self.async_client = httpx.AsyncClient(timeout=180.0)

    def make_request(self, prompt: str, user_id: str = "core_system") -> str:
        """
        Sends a prompt to the configured Chat Completions API. (Synchronous)
        """
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

    # --- THIS IS THE UPGRADE (Part 2 of 2) ---
    # A new, async version of the make_request method.
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


class OrchestratorClient(BaseLLMClient):
    """
    Client for the Orchestrator LLM (e.g., GPT-4, Claude 3).
    Responsible for high-level planning and intent interpretation.
    """

    def __init__(self):
        super().__init__(
            api_url=settings.ORCHESTRATOR_API_URL,
            api_key=settings.ORCHESTRATOR_API_KEY,
            model_name=settings.ORCHESTRATOR_MODEL_NAME,
        )
        log.info(f"OrchestratorClient initialized for model '{self.model_name}'.")


class GeneratorClient(BaseLLMClient):
    """
    Client for the Generator LLM (e.g., a specialized coding model).
    Responsible for code generation and detailed implementation.
    """

    def __init__(self):
        """Initialize the LLM client with API URL, key, and model name, setting up headers and async client."""
        super().__init__(
            api_url=settings.GENERATOR_API_URL,
            api_key=settings.GENERATOR_API_KEY,
            model_name=settings.GENERATOR_MODEL_NAME,
        )
        log.info(f"GeneratorClient initialized for model '{self.model_name}'.")
