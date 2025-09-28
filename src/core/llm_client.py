# src/core/llm_client.py
"""
A dedicated, asynchronous client for interacting with LLM APIs.
"""
from __future__ import annotations

from pathlib import Path

import httpx

from shared.logger import getLogger

logger = getLogger(Path(__file__).stem)


# ID: 2dce5867-b6f5-49ee-9419-5c548bbaeebd
class LLMClient:
    """A wrapper for making asynchronous API calls to a specific LLM."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        model_name: str,
        http_timeout: int = 60,
    ):
        self.api_url = api_url
        self.api_key = api_key
        self.model_name = model_name
        self.http_timeout = http_timeout
        self.base_url = api_url  # For compatibility with test assertions

    # ID: cf51233c-d53a-4f83-bfbf-c694e91e2fb1
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
        # This payload structure is common for OpenAI-compatible APIs
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
                    f"Making request to {self.api_url} with model {self.model_name}"
                )
                response = await client.post(
                    self.api_url, headers=headers, json=payload
                )
                response.raise_for_status()  # Raise an exception for bad status codes

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
                    f"HTTP error occurred: {e.response.status_code} - {e.response.text}"
                )
                raise
            except Exception as e:
                logger.error(f"An unexpected error occurred during LLM request: {e}")
                raise
