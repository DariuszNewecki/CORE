# src/core/clients.py
"""
Clients for communicating with the different LLMs in the CORE ecosystem.
This version is updated to use the modern "Chat Completions" API format,
which is compatible with providers like DeepSeek and OpenAI's newer models.
"""
import os
import requests
from typing import Dict, Any

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
        # Ensure the URL ends with the correct endpoint for compatibility
        if not api_url.endswith("/v1/chat/completions") and not api_url.endswith(
            "/chat/completions"
        ):
            self.api_url = api_url.rstrip("/") + "/v1/chat/completions"
        else:
            self.api_url = api_url

        self.model_name = model_name
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def make_request(self, prompt: str, user_id: str = "core_system") -> str:
        """
        Sends a prompt to the configured Chat Completions API.

        Args:
            prompt (str): The prompt to send to the LLM. It will be wrapped as a
                'user' message.
            user_id (str): Optional identifier for the requester (used by some APIs
                for moderation).

        Returns:
            str: The text content from the LLM's response, or an error message.

        Raises:
            requests.HTTPError: If the API returns a non-200 status code.
        """
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "user": user_id,
        }

        try:
            log.debug(f"Sending request to {self.api_url} for model {self.model_name}...")
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
                f"Network error during LLM request to {self.api_url}: {e}", exc_info=True
            )
            return f"Error: Could not connect to LLM endpoint. Details: {e}"
        except (KeyError, IndexError):
            log.error(
                f"Error parsing LLM response. Full response: {response.text}",
                exc_info=True,
            )
            return "Error: Could not parse response from API."


class OrchestratorClient(BaseLLMClient):
    """
    Client for the Orchestrator LLM (e.g., GPT-4, Claude 3).
    Responsible for high-level planning and intent interpretation.
    """

    def __init__(self):
        """
        Initialize the OrchestratorClient using environment variables.
        """
        super().__init__(
            api_url=os.getenv("ORCHESTRATOR_API_URL"),
            api_key=os.getenv("ORCHESTRATOR_API_KEY"),
            model_name=os.getenv("ORCHESTRATOR_MODEL_NAME", "deepseek-chat"),
        )
        log.info(f"OrchestratorClient initialized for model '{self.model_name}'.")


class GeneratorClient(BaseLLMClient):
    """
    Client for the Generator LLM (e.g., a specialized coding model).
    Responsible for code generation and detailed implementation.
    """

    def __init__(self):
        """
        Initialize the GeneratorClient using environment variables.
        """
        super().__init__(
            api_url=os.getenv("GENERATOR_API_URL"),
            api_key=os.getenv("GENERATOR_API_KEY"),
            model_name=os.getenv("GENERATOR_MODEL_NAME", "deepseek-coder"),
        )
        log.info(f"GeneratorClient initialized for model '{self.model_name}'.")