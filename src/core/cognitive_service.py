# src/core/cognitive_service.py
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from services.config_service import config_service
from services.database.models import CognitiveRole, LlmResource
from services.database.session_manager import get_session
from services.llm.client import LLMClient
from services.llm.providers.base import AIProvider
from services.llm.providers.ollama import OllamaProvider
from services.llm.providers.openai import OpenAIProvider
from services.llm.resource_selector import ResourceSelector
from shared.logger import getLogger
from sqlalchemy import select

log = getLogger(__name__)


# ID: 507c1d3a-e014-4695-a5c6-2e50f2d8dd4d
class CognitiveService:
    """
    Manages LLM client lifecycle and provides clients for specific cognitive roles.
    Acts as a factory for creating provider-specific clients.
    """

    def __init__(self, repo_path: Path):
        self._repo_path = Path(repo_path)
        self._loaded: bool = False
        self._clients_by_role: dict[str, LLMClient] = {}
        self._resource_selector: ResourceSelector | None = None
        self._init_lock = asyncio.Lock()
        # Lazy import pattern to avoid import-time side effects in tests
        self.qdrant_service = __import__(
            "services.clients.qdrant_client"
        ).clients.qdrant_client.QdrantService()

    # ID: 68895785-8f99-4c02-9167-7191e35a0a98
    async def initialize(self) -> None:
        """Load resources and roles from DB and prepare the selector."""
        async with self._init_lock:
            if self._loaded:
                return

            try:
                log.info("Initializing CognitiveService from database...")
                async with get_session() as session:
                    res_result = await session.execute(select(LlmResource))
                    role_result = await session.execute(select(CognitiveRole))
                    resources = list(res_result.scalars().all())
                    roles = list(role_result.scalars().all())

                self._resource_selector = ResourceSelector(resources, roles)
                self._loaded = True
                log.info(
                    f"CognitiveService loaded {len(resources)} resources and {len(roles)} roles."
                )
            except Exception as e:
                log.warning(
                    f"DB init failed for CognitiveService ({e}); using empty selector."
                )
                self._resource_selector = ResourceSelector([], [])

    async def _create_provider_for_resource(self, resource: LlmResource) -> AIProvider:
        """
        Create the correct provider. Config is fetched from DB-backed config service.

        UPDATED: Now uses encrypted secrets for API keys!
        """
        prefix = (resource.env_prefix or "").strip().upper()
        if not prefix:
            raise ValueError(f"Resource '{resource.name}' is missing env_prefix.")

        # Get non-secret config (URLs, model names) from config service
        api_url = await config_service.get(f"{prefix}_API_URL") or os.getenv(
            f"{prefix}_API_URL"
        )
        model_name = await config_service.get(f"{prefix}_MODEL_NAME") or os.getenv(
            f"{prefix}_MODEL_NAME"
        )

        # Get API key from ENCRYPTED secrets storage
        api_key = None
        try:
            # Try to get from encrypted secrets first
            api_key = await config_service.get_secret(
                f"{prefix}_API_KEY", audit_context=f"cognitive_service:{resource.name}"
            )
            log.debug(f"Retrieved encrypted API key for {resource.name}")
        except KeyError:
            # Fallback to environment variable (for backwards compatibility during migration)
            api_key = os.getenv(f"{prefix}_API_KEY")
            if api_key:
                log.warning(
                    f"Using API key from environment for {resource.name}. "
                    f"Consider migrating to encrypted storage: "
                    f"core-admin secrets set {prefix}_API_KEY"
                )

        if not api_url or not model_name:
            raise ValueError(
                f"Missing required config for resource '{resource.name}' with prefix '{prefix}_'. "
                "Ensure URL and model_name are configured."
            )

        # Simple provider routing
        if "ollama" in resource.name.lower() or "11434" in (api_url or ""):
            return OllamaProvider(
                api_url=api_url, model_name=model_name, api_key=api_key
            )

        # Default to OpenAI-compatible (or OpenAI proxy)
        return OpenAIProvider(api_url=api_url, model_name=model_name, api_key=api_key)

    # ID: 8c6c595c-d01b-4eb2-b2ad-3035ec35b480
    async def aget_client_for_role(self, role_name: str) -> LLMClient:
        """Return an LLM client for the given cognitive role."""
        if not self._loaded:
            await self.initialize()

        if role_name in self._clients_by_role:
            return self._clients_by_role[role_name]

        if not self._resource_selector:
            raise RuntimeError("ResourceSelector not initialized.")

        resource = self._resource_selector.select_resource_for_role(role_name)
        if not resource:
            raise RuntimeError(f"No compatible resource found for role '{role_name}'")

        try:
            # Create provider (gets config and API keys from database)
            provider = await self._create_provider_for_resource(resource)

            # Create resource config for rate limiting, etc. using global config_service
            from services.config_service import LLMResourceConfig

            resource_config = LLMResourceConfig(config_service, resource.name)

            # Create client with both provider and config
            client = LLMClient(provider, resource_config)

            # Initialize rate limiting (normally done by create() factory method)
            max_concurrent = await resource_config.get_max_concurrent()
            client._semaphore = asyncio.Semaphore(max_concurrent)

            log.info(
                f"Initialized LLMClient for {resource.name} "
                f"(model={provider.model_name}, max_concurrent={max_concurrent})"
            )

            self._clients_by_role[role_name] = client
            return client
        except Exception as e:
            raise RuntimeError(
                f"Failed to create client for role '{role_name}': {e}"
            ) from e

    # ID: 13aabd89-2e2b-49a1-94d9-3a4e8bbd434b
    async def get_embedding_for_code(self, source_code: str) -> list[float] | None:
        """Generate an embedding using the Vectorizer role."""
        if not source_code:
            return None
        client = await self.aget_client_for_role("Vectorizer")
        return await client.get_embedding(source_code)

    # ID: 483b9bac-982f-484d-8cec-18354a9f422d
    async def search_capabilities(
        self, query: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Semantic search via Qdrant."""
        if not self._loaded:
            await self.initialize()

        try:
            query_vector = await self.get_embedding_for_code(query)
            if not query_vector:
                return []
            return await self.qdrant_service.search_similar(query_vector, limit=limit)
        except Exception as e:
            log.error(f"Semantic search failed: {e}", exc_info=True)
            return []
