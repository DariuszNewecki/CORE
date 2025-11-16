# src/services/llm/client.py

"""
A simplified LLM Client that acts as a facade over a specific AI provider.

NOW USES: Database-backed configuration instead of environment variables.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

from services.config_service import ConfigService, LLMResourceConfig
from shared.logger import getLogger
from sqlalchemy.ext.asyncio import AsyncSession

from .providers.base import AIProvider

logger = getLogger(__name__)


# ID: 3bbee275-19fe-4823-a424-33c41b25d52d
class LLMClient:
    """
    A client that uses a provider strategy to interact with an LLM API.

    UPDATED: Now reads configuration from database instead of environment variables.
    """

    def __init__(self, provider: AIProvider, resource_config: LLMResourceConfig):
        self.provider = provider
        self.resource_config = resource_config
        self.model_name = provider.model_name
        self._semaphore: asyncio.Semaphore | None = None
        self._last_request_time: float = 0

    @classmethod
    # ID: c9aaf69f-39ba-42b4-aa9a-96c07e8e8588
    async def create(
        cls, db: AsyncSession, provider: AIProvider, resource_name: str
    ) -> LLMClient:
        """
        Factory method to create LLMClient with database configuration.

        Args:
            db: Database session
            provider: Configured AI provider instance
            resource_name: Name of the LLM resource (e.g., "anthropic", "deepseek_chat")

        Returns:
            Configured LLMClient instance

        Usage:
            config = await ConfigService.create(db)
            resource_config = await LLMResourceConfig.for_resource(config, "anthropic")

            provider = AnthropicProvider(
                api_key=await resource_config.get_api_key(),
                model_name=await resource_config.get_model_name(),
            )

            client = await LLMClient.create(db, provider, "anthropic")
        """
        config = await ConfigService.create(db)
        resource_config = await LLMResourceConfig.for_resource(config, resource_name)
        instance = cls(provider, resource_config)
        max_concurrent = await resource_config.get_max_concurrent()
        instance._semaphore = asyncio.Semaphore(max_concurrent)
        logger.info(
            f"Initialized LLMClient for {resource_name} (model={provider.model_name}, max_concurrent={max_concurrent})"
        )
        return instance

    async def _enforce_rate_limit(self):
        """Enforce rate limiting based on database configuration."""
        rate_limit = await self.resource_config.get_rate_limit()
        if rate_limit > 0:
            now = asyncio.get_event_loop().time()
            time_since_last = now - self._last_request_time
            if time_since_last < rate_limit:
                wait_time = rate_limit - time_since_last
                logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
            self._last_request_time = asyncio.get_event_loop().time()

    async def _request_with_retry(self, method, *args, **kwargs) -> Any:
        """
        Generic retry logic with concurrency control.

        Enforces:
        - Max concurrent requests (via semaphore)
        - Rate limiting (via delay between requests)
        - Exponential backoff on failures
        """
        if not self._semaphore:
            raise RuntimeError(
                "LLMClient not properly initialized - use create() factory method"
            )
        backoff_delays = [1.0, 2.0, 4.0]
        async with self._semaphore:
            await self._enforce_rate_limit()
            for attempt in range(len(backoff_delays) + 1):
                try:
                    return await method(*args, **kwargs)
                except Exception as e:
                    error_message = f"Request failed (attempt {attempt + 1}/{len(backoff_delays) + 1}): {type(e).__name__} - {e}"
                    if attempt < len(backoff_delays):
                        wait_time = backoff_delays[attempt] + random.uniform(0, 0.5)
                        logger.warning(
                            f"{error_message}. Retrying in {wait_time:.1f}s..."
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    logger.error(
                        f"Final attempt failed: {error_message}", exc_info=True
                    )
                    raise

    # ID: 94b27523-b60f-4ce3-a5df-ea2b98b19835
    async def make_request_async(
        self, prompt: str, user_id: str = "core_system"
    ) -> str:
        """Makes a chat completion request using the configured provider with retries."""
        return await self._request_with_retry(
            self.provider.chat_completion, prompt, user_id
        )

    # ID: f740d19b-ee4d-41ec-82c1-80049d22e872
    async def get_embedding(self, text: str) -> list[float]:
        """Gets an embedding using the configured provider with retries."""
        return await self._request_with_retry(self.provider.get_embedding, text)


# ID: 141f3410-1bd3-485f-a69d-827b0876af78
async def create_llm_client_for_role(
    db: AsyncSession, cognitive_role: str
) -> LLMClient:
    """
    Factory function to create an LLM client for a specific cognitive role.

    This reads the role's assigned LLM resource from the database and
    creates an appropriately configured client.

    Args:
        db: Database session
        cognitive_role: Role name (e.g., "planner", "coder")

    Returns:
        Configured LLMClient instance

    Raises:
        ValueError: If role not found or not assigned to a resource

    Usage:
        client = await create_llm_client_for_role(db, "planner")
        response = await client.make_request_async("Plan this task...")
    """
    from sqlalchemy import text

    query = text(
        "\n        SELECT assigned_resource\n        FROM core.cognitive_roles\n        WHERE role = :role AND is_active = true\n    "
    )
    result = await db.execute(query, {"role": cognitive_role})
    row = result.fetchone()
    if not row or not row[0]:
        raise ValueError(
            f"Cognitive role '{cognitive_role}' not found or not assigned to a resource"
        )
    resource_name = row[0]
    config = await ConfigService.create(db)
    resource_config = await LLMResourceConfig.for_resource(config, resource_name)
    api_url = await resource_config.get_api_url()
    api_key = await resource_config.get_api_key(audit_context=cognitive_role)
    model_name = await resource_config.get_model_name()
    if "anthropic" in api_url:
        from .providers.anthropic import AnthropicProvider

        provider = AnthropicProvider(api_key=api_key, model_name=model_name)
    elif "deepseek" in api_url:
        from .providers.openai import OpenAIProvider

        provider = OpenAIProvider(
            api_url=api_url, api_key=api_key, model_name=model_name
        )
    elif "ollama" in api_url or "11434" in api_url:
        from .providers.ollama import OllamaProvider

        provider = OllamaProvider(api_url=api_url, model_name=model_name)
    else:
        from .providers.openai import OpenAIProvider

        provider = OpenAIProvider(
            api_url=api_url, api_key=api_key, model_name=model_name
        )
    return await LLMClient.create(db, provider, resource_name)
