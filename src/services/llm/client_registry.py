# src/services/llm/client_registry.py

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

from services.config_service import ConfigService, LLMResourceConfig
from services.database.models import LlmResource
from services.database.session_manager import get_session
from services.llm.client import LLMClient
from shared.logger import getLogger

logger = getLogger(__name__)


# ID: 73176353-f439-4aa3-bea6-be2b907aa0e3
class CachedConfigService:
    """
    A ConfigService impersonator that serves values from a static cache.
    Used to provide configuration to LLMResourceConfig without holding open DB sessions.
    """

    def __init__(self, cache: dict[str, Any]):
        self._cache = cache

    # ID: 67de48ce-a1f4-462f-99be-2d34ed31711c
    async def get(
        self, key: str, default: str | None = None, required: bool = False
    ) -> str | None:
        val = self._cache.get(key)
        if val is None:
            if required:
                raise KeyError(f"Key {key} not found in cache")
            return default
        return val

    # ID: e373f8cd-a149-46c5-9382-a35b3875fe23
    async def get_secret(self, key: str, audit_context: str | None = None) -> str:
        raise NotImplementedError("CachedConfigService does not support secrets")


# ID: 92a5f45c-cc8f-4d98-af41-302c6b128e1c
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

    # ID: 23b25c3c-e14b-40a4-bd2f-1ae41f813499
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
                logger.debug(f"Returning cached client for {resource.name}")
                return self._clients[resource.name]

            logger.info(f"Creating new client for {resource.name}")
            provider = await provider_factory(resource)

            # FIX: Load config into memory to avoid Session lifecycle issues
            # We perform a read-only sync of config values needed for client behavior
            # (timeouts, concurrency limits) so the client doesn't need an active DB connection
            async with get_session() as session:
                real_config_service = await ConfigService.create(session)
                # Copy the cache so we can close the session safely
                config_cache = dict(real_config_service._cache)

            # Use the cached service wrapper to satisfy LLMResourceConfig interface
            cached_service = CachedConfigService(config_cache)
            # We suppress type checking here because CachedConfigService duck-types ConfigService
            resource_config = LLMResourceConfig(cached_service, resource.name)  # type: ignore

            client = LLMClient(provider, resource_config)

            # Initialize semaphore based on config now, while we have the cache
            max_concurrent = await resource_config.get_max_concurrent()
            client._semaphore = asyncio.Semaphore(max_concurrent)

            logger.info(
                f"Initialized LLMClient for {resource.name} (model={provider.model_name}, max_concurrent={max_concurrent})"
            )
            self._clients[resource.name] = client
            return client

    # ID: 9725a2e8-decb-482e-b7a3-18728e3c1c01
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

    # ID: 18efb3c8-3bfb-4622-8459-ffcc2f9c5a7d
    def clear_cache(self) -> None:
        """
        Clear all cached clients.

        Useful for:
        - Testing
        - Resource cleanup
        - Configuration changes requiring fresh clients
        """
        logger.info(f"Clearing {len(self._clients)} cached clients")
        self._clients.clear()

    # ID: 91a0c580-cb8f-48fa-a28d-bfe5c72dec8f
    def get_cached_resource_names(self) -> list[str]:
        """
        Get list of resource names currently in cache.

        Returns:
            List of resource names with cached clients
        """
        return list(self._clients.keys())
