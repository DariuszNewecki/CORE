# src/services/llm/client.py (UPDATED VERSION)
"""
A simplified LLM Client that acts as a facade over a specific AI provider.

NOW USES: Database-backed configuration instead of environment variables.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from services.config_service import ConfigService, LLMResourceConfig
from shared.logger import getLogger

from .providers.base import AIProvider

log = getLogger(__name__)


# ID: 8a9f272d-4f69-48f0-bda3-b485446bfc37
class LLMClient:
    """
    A client that uses a provider strategy to interact with an LLM API.

    UPDATED: Now reads configuration from database instead of environment variables.
    """

    def __init__(
        self,
        provider: AIProvider,
        resource_config: LLMResourceConfig,
    ):
        self.provider = provider
        self.resource_config = resource_config
        self.model_name = provider.model_name

        # Rate limiting state
        self._semaphore: asyncio.Semaphore | None = None
        self._last_request_time: float = 0

    @classmethod
    async def create(
        cls,
        db: AsyncSession,
        provider: AIProvider,
        resource_name: str,
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

        # Initialize rate limiting based on DB config
        max_concurrent = await resource_config.get_max_concurrent()
        instance._semaphore = asyncio.Semaphore(max_concurrent)

        log.info(
            f"Initialized LLMClient for {resource_name} "
            f"(model={provider.model_name}, max_concurrent={max_concurrent})"
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
                log.debug(f"Rate limiting: waiting {wait_time:.2f}s")
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

        async with self._semaphore:  # Enforce max concurrent
            await self._enforce_rate_limit()  # Enforce rate limit

            for attempt in range(len(backoff_delays) + 1):
                try:
                    return await method(*args, **kwargs)
                except Exception as e:
                    error_message = (
                        f"Request failed (attempt {attempt + 1}/{len(backoff_delays) + 1}): "
                        f"{type(e).__name__} - {e}"
                    )

                    if attempt < len(backoff_delays):
                        wait_time = backoff_delays[attempt] + random.uniform(0, 0.5)
                        log.warning(f"{error_message}. Retrying in {wait_time:.1f}s...")
                        await asyncio.sleep(wait_time)
                        continue

                    log.error(f"Final attempt failed: {error_message}", exc_info=True)
                    raise

    # ID: 1c0b0c26-46a8-4559-9b73-0b8a429a1303
    async def make_request_async(
        self, prompt: str, user_id: str = "core_system"
    ) -> str:
        """Makes a chat completion request using the configured provider with retries."""
        return await self._request_with_retry(
            self.provider.chat_completion, prompt, user_id
        )

    # ID: 262ea6eb-241e-444d-8388-aab25b9b5fa8
    async def get_embedding(self, text: str) -> list[float]:
        """Gets an embedding using the configured provider with retries."""
        return await self._request_with_retry(self.provider.get_embedding, text)


# ID: llm-client-factory-001
async def create_llm_client_for_role(
    db: AsyncSession,
    cognitive_role: str,
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

    # Get the assigned resource for this role
    query = text(
        """
        SELECT assigned_resource
        FROM core.cognitive_roles
        WHERE role = :role AND is_active = true
    """
    )

    result = await db.execute(query, {"role": cognitive_role})
    row = result.fetchone()

    if not row or not row[0]:
        raise ValueError(
            f"Cognitive role '{cognitive_role}' not found or not assigned to a resource"
        )

    resource_name = row[0]

    # Get resource configuration
    config = await ConfigService.create(db)
    resource_config = await LLMResourceConfig.for_resource(config, resource_name)

    # Determine provider type and create appropriate provider instance
    api_url = await resource_config.get_api_url()
    api_key = await resource_config.get_api_key(audit_context=cognitive_role)
    model_name = await resource_config.get_model_name()

    # Import appropriate provider based on API URL
    if "anthropic" in api_url:
        from .providers.anthropic import AnthropicProvider

        provider = AnthropicProvider(api_key=api_key, model_name=model_name)
    elif "deepseek" in api_url:
        from .providers.openai import (
            OpenAIProvider,
        )

        provider = OpenAIProvider(
            api_url=api_url, api_key=api_key, model_name=model_name
        )
    elif "ollama" in api_url or "11434" in api_url:
        from .providers.ollama import OllamaProvider

        provider = OllamaProvider(api_url=api_url, model_name=model_name)
    else:
        # Default to OpenAI-compatible
        from .providers.openai import OpenAIProvider

        provider = OpenAIProvider(
            api_url=api_url, api_key=api_key, model_name=model_name
        )

    # Create and return client
    return await LLMClient.create(db, provider, resource_name)
