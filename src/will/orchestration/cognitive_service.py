# src/will/orchestration/cognitive_service.py

"""
Provides the CognitiveService, which orchestrates LLM interactions.
Refactored for A2 Autonomy: Enforces Dependency Injection for QdrantService.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from services.config_service import ConfigService
from services.database.models import CognitiveRole, LlmResource
from services.database.session_manager import get_session
from services.llm.client import LLMClient
from services.llm.providers.base import AIProvider
from services.llm.providers.ollama import OllamaProvider
from services.llm.providers.openai import OpenAIProvider
from shared.logger import getLogger
from will.agents.resource_selector import ResourceSelector

if TYPE_CHECKING:
    from services.clients.qdrant_client import QdrantService

logger = getLogger(__name__)


# ID: ea9c83f1-8266-44ab-ad6b-e4333dc52416
class CognitiveService:
    """
    Manages LLM client lifecycle and provides clients for specific cognitive roles.
    Acts as a factory for creating provider-specific clients.
    """

    def __init__(self, repo_path: Path, qdrant_service: QdrantService | None = None):
        """
        Initialize CognitiveService.

        Args:
            repo_path: Path to the repository root.
            qdrant_service: Singleton QdrantService instance. Injected to prevent
                          split-brain states. If None, semantic search capabilities
                          will raise an error if accessed.
        """
        self._repo_path = Path(repo_path)
        self._loaded: bool = False
        self._clients_by_role: dict[str, LLMClient] = {}
        self._resources: list[LlmResource] = []
        self._roles: list[CognitiveRole] = []
        self._init_lock = asyncio.Lock()
        self._config_service: ConfigService | None = None

        # DI: Store the injected service
        self._qdrant_service = qdrant_service

    @property
    # ID: 1ecf260d-148e-49fc-b446-efbb3ecea178
    def qdrant_service(self) -> QdrantService:
        """
        Access the injected QdrantService.
        Raises RuntimeError if it wasn't provided during initialization.
        """
        if self._qdrant_service is None:
            raise RuntimeError(
                "QdrantService was not injected into CognitiveService. "
                "This capability requires a fully wired service via ServiceRegistry."
            )
        return self._qdrant_service

    # ID: 2e16bd1a-066c-401d-b835-60b05887963b
    async def initialize(self) -> None:
        """Load resources and roles from DB and prepare the selector."""
        async with self._init_lock:
            if self._loaded:
                return
            try:
                logger.info("Initializing CognitiveService from database...")
                async with get_session() as session:
                    self._config_service = await ConfigService.create(session)
                    res_result = await session.execute(select(LlmResource))
                    role_result = await session.execute(select(CognitiveRole))
                    self._resources = list(res_result.scalars().all())
                    self._roles = list(role_result.scalars().all())
                self._loaded = True
                logger.info(
                    f"CognitiveService loaded {len(self._resources)} resources and {len(self._roles)} roles."
                )
            except Exception as e:
                logger.warning(
                    f"DB init failed for CognitiveService ({e}); using empty lists."
                )
                self._resources = []
                self._roles = []
                self._loaded = True

    async def _create_provider_for_resource(self, resource: LlmResource) -> AIProvider:
        """
        Create the correct provider. Config is fetched from DB-backed config service.
        """
        prefix = (resource.env_prefix or "").strip().upper()
        if not prefix:
            raise ValueError(f"Resource '{resource.name}' is missing env_prefix.")
        if not self._config_service:
            async with get_session() as session:
                self._config_service = await ConfigService.create(session)
        api_url = await self._config_service.get(f"{prefix}_API_URL") or os.getenv(
            f"{prefix}_API_URL"
        )
        model_name = await self._config_service.get(
            f"{prefix}_MODEL_NAME"
        ) or os.getenv(f"{prefix}_MODEL_NAME")
        api_key = None
        try:
            api_key = await self._config_service.get_secret(
                f"{prefix}_API_KEY", audit_context=f"cognitive_service:{resource.name}"
            )
            logger.debug(f"Retrieved encrypted API key for {resource.name}")
        except (KeyError, ValueError) as e:
            api_key = os.getenv(f"{prefix}_API_KEY")
            if not api_key:
                if (
                    "local" in resource.name.lower()
                    or "ollama" in resource.name.lower()
                ):
                    logger.debug(
                        f"No API key needed for local resource {resource.name}"
                    )
                    api_key = None
                else:
                    logger.warning(
                        f"No API key found for {resource.name}. Set it with: core-admin secrets set {prefix}_API_KEY"
                    )
        if not api_url or not model_name:
            raise ValueError(
                f"Missing required config for resource '{resource.name}' with prefix '{prefix}_'. Ensure URL and model_name are configured."
            )
        if "ollama" in resource.name.lower() or "11434" in (api_url or ""):
            return OllamaProvider(
                api_url=api_url, model_name=model_name, api_key=api_key
            )
        return OpenAIProvider(api_url=api_url, model_name=model_name, api_key=api_key)

    # ID: 802e6346-d3d7-43f4-a34a-4ba0c3bd47e3
    async def aget_client_for_role(self, role_name: str) -> LLMClient:
        """Return an LLM client for the given cognitive role."""
        if not self._loaded:
            await self.initialize()
        if role_name in self._clients_by_role:
            return self._clients_by_role[role_name]
        if not self._resources or not self._roles:
            raise RuntimeError("Resources and roles not initialized.")
        resource = ResourceSelector.select_resource_for_role(
            role_name, self._roles, self._resources
        )
        if not resource:
            raise RuntimeError(f"No compatible resource found for role '{role_name}'")
        try:
            provider = await self._create_provider_for_resource(resource)
            from services.config_service import LLMResourceConfig

            if not self._config_service:
                async with get_session() as session:
                    self._config_service = await ConfigService.create(session)
            resource_config = LLMResourceConfig(self._config_service, resource.name)
            client = LLMClient(provider, resource_config)
            max_concurrent = await resource_config.get_max_concurrent()
            client._semaphore = asyncio.Semaphore(max_concurrent)
            logger.info(
                f"Initialized LLMClient for {resource.name} (model={provider.model_name}, max_concurrent={max_concurrent})"
            )
            self._clients_by_role[role_name] = client
            return client
        except Exception as e:
            raise RuntimeError(
                f"Failed to create client for role '{role_name}': {e}"
            ) from e

    # ID: 14438269-162b-4b60-b9ca-bd3f4aa2a3dd
    async def get_embedding_for_code(self, source_code: str) -> list[float] | None:
        """Generate an embedding using the Vectorizer role."""
        if not source_code:
            return None
        client = await self.aget_client_for_role("Vectorizer")
        return await client.get_embedding(source_code)

    # ID: e07ce6fa-8d5f-43c8-844b-16bb1d07f99a
    async def search_capabilities(
        self, query: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Semantic search via Qdrant."""
        if not self._loaded:
            await self.initialize()
        try:
            # This line will now RAISE if qdrant_service wasn't injected
            # This is INTENTIONAL to catch split-brain usage
            query_vector = await self.get_embedding_for_code(query)
            if not query_vector:
                return []
            return await self.qdrant_service.search_similar(query_vector, limit=limit)
        except Exception as e:
            logger.error(f"Semantic search failed: {e}", exc_info=True)
            return []
