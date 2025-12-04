# src/services/llm/client_orchestrator.py

"""
Will component: Orchestrates LLM client selection and lifecycle.

This is the decision-making layer that:
1. Reads Mind (roles and resources from database)
2. Uses ResourceSelector to choose appropriate resources
3. Delegates client creation to ClientRegistry (Body)

Part of Mind-Body-Will architecture:
- Mind: Database + .intent/ policies
- Body: ClientRegistry (pure execution)
- Will: ClientOrchestrator (this file - decision making)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from services.config_service import ConfigService
from services.database.models import CognitiveRole, LlmResource
from services.database.session_manager import get_session
from services.llm.client import LLMClient
from services.llm.client_registry import LLMClientRegistry
from services.llm.providers.base import AIProvider
from services.llm.providers.ollama import OllamaProvider
from services.llm.providers.openai import OpenAIProvider
from shared.logger import getLogger
from sqlalchemy import select
from will.agents.resource_selector import ResourceSelector

logger = getLogger(__name__)


# ID: 82bf854c-619c-4f81-815f-b94c8d0a1696
class ClientOrchestrator:
    """
    Will: Orchestrates LLM client selection and provisioning.

    Responsibilities:
    - Load Mind state (roles and resources from database)
    - Decide which resource to use for which role
    - Coordinate with Body (ClientRegistry) to get clients
    - Create providers when needed

    Does NOT:
    - Manage client lifecycle (that's Body's job)
    - Store clients directly (delegates to registry)
    """

    def __init__(self, repo_path: Path):
        """
        Initialize orchestrator.

        Args:
            repo_path: Path to repository root (for context, not used directly)
        """
        self._repo_path = Path(repo_path)
        self._loaded = False
        self._resources: list[LlmResource] = []
        self._roles: list[CognitiveRole] = []
        self._client_registry = LLMClientRegistry()
        self._init_lock = asyncio.Lock()
        # Cache for non-secret config to avoid DB thrashing
        self._config_cache: dict[str, Any] = {}

    # ID: afff714a-8e04-4c35-97c7-11bda8507c92
    async def initialize(self) -> None:
        """
        Load Mind state: Read roles and resources from database.
        """
        async with self._init_lock:
            if self._loaded:
                return
            try:
                logger.info("ClientOrchestrator: Loading Mind state from database...")
                async with get_session() as session:
                    # Pre-load config cache for efficiency
                    temp_config = await ConfigService.create(session)
                    self._config_cache = temp_config._cache

                    res_result = await session.execute(select(LlmResource))
                    role_result = await session.execute(select(CognitiveRole))
                    self._resources = list(res_result.scalars().all())
                    self._roles = list(role_result.scalars().all())
                self._loaded = True
                logger.info(
                    f"ClientOrchestrator loaded {len(self._resources)} resources and {len(self._roles)} roles from Mind"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to load Mind state from database ({e}); using empty lists"
                )
                self._resources = []
                self._roles = []
                self._loaded = True

    # ID: cabc9e05-454e-4ac3-87e6-5d017c1d1d31
    async def get_client_for_role(self, role_name: str) -> LLMClient:
        """
        Will: Decide which resource to use for a role, then get client.
        """
        if not self._loaded:
            await self.initialize()
        if not self._resources or not self._roles:
            raise RuntimeError("Resources and roles not initialized (Mind not loaded)")

        resource = ResourceSelector.select_resource_for_role(
            role_name, self._roles, self._resources
        )
        if not resource:
            raise RuntimeError(
                f"No compatible resource found for role '{role_name}' (Mind does not have a suitable resource configured)"
            )
        logger.debug(
            f"Orchestrator: Selected resource '{resource.name}' for role '{role_name}'"
        )

        # ID: fd5528a7-7e30-47af-9741-ca1a17fd555d
        async def provider_factory(res: LlmResource) -> AIProvider:
            return await self._create_provider_for_resource(res)

        try:
            client = await self._client_registry.get_or_create_client(
                resource, provider_factory
            )
            return client
        except Exception as e:
            raise RuntimeError(
                f"Failed to provision client for role '{role_name}': {e}"
            ) from e

    async def _create_provider_for_resource(self, resource: LlmResource) -> AIProvider:
        """
        Create the correct provider for a resource based on its configuration.
        """
        prefix = (resource.env_prefix or "").strip().upper()
        if not prefix:
            raise ValueError(
                f"Resource '{resource.name}' is missing env_prefix (Mind misconfiguration)"
            )

        # Use a fresh session for secret retrieval to ensure connection safety
        async with get_session() as session:
            # Rehydrate config service with cached non-secrets + new session for secrets
            config = ConfigService(session, self._config_cache)

            # --- UPDATED LOGIC: STRICT DATABASE CONFIGURATION ---
            api_url = await config.get(f"{prefix}_API_URL")

            # Fail fast if missing from DB
            if not api_url:
                raise ValueError(
                    f"Configuration '{prefix}_API_URL' is missing from the Database. "
                    f"Run 'poetry run core-admin manage dotenv sync --write' to populate "
                    "runtime settings from your .env file."
                )

            model_name = await config.get(f"{prefix}_MODEL_NAME")
            if not model_name:
                raise ValueError(
                    f"Configuration '{prefix}_MODEL_NAME' is missing from the Database. "
                    f"Run 'poetry run core-admin manage dotenv sync --write'."
                )

            api_key = None
            try:
                api_key = await config.get_secret(
                    f"{prefix}_API_KEY",
                    audit_context=f"client_orchestrator:{resource.name}",
                )
            except KeyError:
                # Fallback for non-secret API keys (rare) or local models
                pass

        # --- Provider Selection Logic ---

        # 1. Anthropic (Claude)
        if "anthropic" in api_url.lower():
            logger.info(f"Creating AnthropicProvider for {resource.name}")
            from services.llm.providers.anthropic import AnthropicProvider

            return AnthropicProvider(
                api_url=api_url, model_name=model_name, api_key=api_key
            )

        # 2. Ollama / Local
        if "ollama" in resource.name.lower() or "11434" in api_url:
            logger.info(f"Creating OllamaProvider for {resource.name}")
            return OllamaProvider(
                api_url=api_url, model_name=model_name, api_key=api_key
            )

        # 3. Default to OpenAI (works for DeepSeek, OpenAI, Azure, etc.)
        logger.info(f"Creating OpenAIProvider for {resource.name}")
        return OpenAIProvider(api_url=api_url, model_name=model_name, api_key=api_key)

    # ID: aae28476-3d3f-428a-a01a-6ae302e119a4
    def get_cached_resource_names(self) -> list[str]:
        """Get list of currently cached resource names."""
        return self._client_registry.get_cached_resource_names()

    # ID: 1b744485-8a18-46cf-9037-04a0fffa4c9b
    async def clear_cache(self) -> None:
        """Clear all cached clients."""
        logger.info("Orchestrator: Clearing client cache")
        self._client_registry.clear_cache()
