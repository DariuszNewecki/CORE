# src/shared/infrastructure/llm/client_registry.py

"""
Pure Body component: Manages LLM client lifecycle without decision-making.
Holds clients, provides them on demand, but doesn't decide which one to use.

This is part of the Mind-Body-Will refactoring to separate concerns:
- Mind: Constitutional rules and policies (database)
- Body: Pure execution without decisions (this file)
- Will: Decision-making and orchestration (agents)
"""

from __future__ import annotations

import asyncio
from typing import Any

from shared.infrastructure.config_service import ConfigService, LLMResourceConfig
from shared.infrastructure.database.models import LlmResource
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.llm.client import LLMClient
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: e6871b0c-f0a1-4c57-ba37-cd45013ebb0a
class CachedConfigService:
    """
    A ConfigService impersonator that serves values from a static cache.
    Used to provide configuration to LLMResourceConfig without holding open DB sessions.
    """

    def __init__(self, cache: dict[str, Any]):
        self._cache = cache

    # ID: 43f0d3fb-bb09-4e3b-a5c9-e04508f2597e
    async def get(
        self, key: str, default: str | None = None, required: bool = False
    ) -> str | None:
        val = self._cache.get(key)
        if val is None:
            if required:
                raise KeyError(f"Key {key} not found in cache")
            return default
        return val

    # ID: 65acad9a-50bf-48d0-b3d0-c1846c2911fc
    async def get_secret(self, key: str, audit_context: str | None = None) -> str:
        raise NotImplementedError("CachedConfigService does not support secrets")


# ID: 9e2b3cb3-fd84-4071-9423-ce0cc38a060b
class LLMClientRegistry:
    """
    Body: Manages LLM client lifecycle without decision-making.

    Responsibilities:
    - Cache client instances by resource name
    - Create new clients using provided factory functions
    - Thread-safe client access via asyncio.Lock

    Does NOT:
    - Decide which resource to use (that's Will's job)
    - Select providers (that's orchestrator's job)
    - Apply any business logic
    """

    def __init__(self):
        """Initialize empty registry with thread-safe access control."""
        self._clients: dict[str, LLMClient] = {}
        self._init_lock = asyncio.Lock()

    # ID: f8ada660-100e-4ea3-a1d5-acdd27a8d0df
    async def get_or_create_client(
        self, resource: LlmResource, provider_factory: callable
    ) -> LLMClient:
        """
        Get cached client or create new one using provided factory.

        Args:
            resource: LlmResource from database (Mind)
            provider_factory: Async function that creates provider for resource

        Returns:
            Configured LLMClient ready to use

        Note:
            This is a pure Body function - it doesn't decide anything,
            just executes the creation logic.
        """
        async with self._init_lock:
            if resource.name in self._clients:
                logger.debug("Returning cached client for %s", resource.name)
                return self._clients[resource.name]
            logger.info("Creating new client for %s", resource.name)
            provider = await provider_factory(resource)
            async with get_session() as session:
                real_config_service = await ConfigService.create(session)
                config_cache = dict(real_config_service._cache)
            cached_service = CachedConfigService(config_cache)
            resource_config = LLMResourceConfig(cached_service, resource.name)
            client = LLMClient(provider, resource_config)
            max_concurrent = await resource_config.get_max_concurrent()
            client._semaphore = asyncio.Semaphore(max_concurrent)
            logger.info(
                "Initialized LLMClient for %s (model=%s, max_concurrent=%s)",
                resource.name,
                provider.model_name,
                max_concurrent,
            )
            self._clients[resource.name] = client
            return client

    # ID: b76b4c50-45bc-490f-a8e1-9e4d45231d15
    def get_cached_client(self, resource_name: str) -> LLMClient | None:
        """
        Simple lookup for cached client.

        Args:
            resource_name: Name of the LLM resource

        Returns:
            Cached client if exists, None otherwise

        Note:
            Pure Body function - no creation, no decisions, just lookup.
        """
        return self._clients.get(resource_name)

    # ID: 78b961fb-593c-4a05-8307-76e4f584417d
    def clear_cache(self) -> None:
        """
        Clear all cached clients.

        Useful for:
        - Testing
        - Resource cleanup
        - Configuration changes requiring fresh clients
        """
        logger.info("Clearing %s cached clients", len(self._clients))
        self._clients.clear()

    # ID: 3ed4248a-f3cb-4388-ad1e-d65511e13fc8
    def get_cached_resource_names(self) -> list[str]:
        """
        Get list of resource names currently in cache.

        Returns:
            List of resource names with cached clients
        """
        return list(self._clients.keys())
