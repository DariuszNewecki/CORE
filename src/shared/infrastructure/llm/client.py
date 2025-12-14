# src/shared/infrastructure/llm/client.py

"""
A simplified LLM Client that acts as a facade over a specific AI provider.

NOW USES: Database-backed configuration instead of environment variables.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.config_service import ConfigService, LLMResourceConfig
from shared.logger import getLogger

from .providers.base import AIProvider


logger = getLogger(__name__)


# ID: 7a329240-1a5e-440b-9c8a-65ad427b5e65
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
    # ID: b93deaf4-7da3-4c67-a4b1-e2a9ae1afeea
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
            "Initialized LLMClient for %s (model=%s, max_concurrent=%s)",
            resource_name,
            provider.model_name,
            max_concurrent,
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
                logger.debug("Rate limiting: waiting %ss", wait_time)
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
                            "%s. Retrying in %ss...", error_message, wait_time
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    logger.error(
                        "Final attempt failed: %s", error_message, exc_info=True
                    )
                    raise

    # ID: 32e259f1-415f-4f2e-9d49-08071b12ceba
    async def make_request_async(
        self, prompt: str, user_id: str = "core_system"
    ) -> str:
        """Makes a chat completion request using the configured provider with retries."""
        return await self._request_with_retry(
            self.provider.chat_completion, prompt, user_id
        )

    # ID: 7e13b689-e8ae-48ac-819b-44f8d3b97e22
    async def get_embedding(self, text: str) -> list[float]:
        """Gets an embedding using the configured provider with retries."""
        return await self._request_with_retry(self.provider.get_embedding, text)


# ID: f0962c2a-eb02-4ef6-856f-413472d3a699
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
