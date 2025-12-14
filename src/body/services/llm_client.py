# src/body/services/llm_client.py

"""
A dedicated, asynchronous client for interacting with LLM APIs.
"""

from __future__ import annotations

import httpx

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: a1cdeb8d-ae98-4891-9b10-c8a571d55443
class LLMClient:
    """A wrapper for making asynchronous API calls to a specific LLM."""

    def __init__(
        self, api_url: str, api_key: str, model_name: str, http_timeout: int = 60
    ):
        self.api_url = api_url
        self.api_key = api_key
        self.model_name = model_name
        self.http_timeout = http_timeout
        self.base_url = api_url

    # ID: e2ceb072-9dbd-4379-bc08-28f7b2df3922
    async def make_request(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        max_tokens: int = 4096,
    ) -> str:
        """
        Makes an asynchronous request to the configured LLM API.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
        }
        async with httpx.AsyncClient(timeout=self.http_timeout) as client:
            try:
                logger.debug(
                    "Making request to %s with model %s", self.api_url, self.model_name
                )
                response = await client.post(
                    self.api_url, headers=headers, json=payload
                )
                response.raise_for_status()
                data = response.json()
                content = (
                    data.get("choices", [{}])[0].get("message", {}).get("content", "")
                )
                if not content:
                    logger.warning("LLM response content is empty.")
                    return ""
                return content.strip()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "HTTP error occurred: %s - %s",
                    e.response.status_code,
                    e.response.text,
                )
                raise
            except Exception as e:
                logger.error("An unexpected error occurred during LLM request: %s", e)
                raise
