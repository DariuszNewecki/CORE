# src/will/orchestration/client_orchestrator.py

"""
Will component: Orchestrates LLM client selection and lifecycle.

This is the decision-making layer that:
1. Reads Mind (roles and resources from database)
2. Uses ResourceSelector to choose appropriate resources
3. Delegates client creation to ClientRegistry (Body)

Part of Mind-Body-Will architecture:
- Mind: Database + .intent/ policies
- Body: ClientRegistry (pure execution), MindStateService (Mind access)
- Will: ClientOrchestrator (this file - decision making)

Constitutional Compliance:
- Will layer: Makes decisions about which resource to use
- Mind/Body/Will separation: Uses MindStateService (Body) for Mind state access
- No direct database access: Receives services via dependency injection
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from body.services.mind_state_service import MindStateService
from shared.infrastructure.config_service import ConfigService
from shared.infrastructure.database.models import CognitiveRole, LlmResource
from shared.infrastructure.llm.client import LLMClient
from shared.infrastructure.llm.client_registry import LLMClientRegistry
from shared.infrastructure.llm.providers.base import AIProvider
from shared.infrastructure.llm.providers.ollama import OllamaProvider
from shared.infrastructure.llm.providers.openai import OpenAIProvider
from shared.logger import getLogger
from will.agents.resource_selector import ResourceSelector


logger = getLogger(__name__)


# ID: 8669d3dc-7233-4b19-a749-120e88f91dee
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

    Constitutional Note:
    This class REQUIRES MindStateService via dependency injection.
    No backward compatibility - this is the constitutional pattern.
    """

    def __init__(self, repo_path: Path, mind_state_service: MindStateService):
        """
        Initialize orchestrator.

        Args:
            repo_path: Path to repository root (for context, not used directly)
            mind_state_service: MindStateService instance for Mind state access

        Constitutional Note:
        mind_state_service is REQUIRED. No fallback, no exceptions.
        """
        self._repo_path = Path(repo_path)
        self._loaded = False
        self._resources: list[LlmResource] = []
        self._roles: list[CognitiveRole] = []
        self._client_registry = LLMClientRegistry()
        self._init_lock = asyncio.Lock()
        self._config_service: ConfigService | None = None
        self._mind_state_service = mind_state_service

    # ID: 519d53bf-45e0-40f3-ba63-47d09369bf46
    async def initialize(self) -> None:
        """
        Load Mind state: Read roles and resources from database.

        Constitutional Note:
        Uses MindStateService (Body) to access Mind state.
        No direct database access - pure dependency injection.
        """
        async with self._init_lock:
            if self._loaded:
                return

            try:
                logger.info("ClientOrchestrator: Loading Mind state from database...")

                # Constitutional compliance: Use Body service
                (
                    resources,
                    roles,
                    config_service,
                ) = await self._mind_state_service.load_mind_state()

                self._resources = resources
                self._roles = roles
                self._config_service = config_service

                self._loaded = True
                logger.info(
                    "ClientOrchestrator loaded %s resources and %s roles from Mind",
                    len(self._resources),
                    len(self._roles),
                )
            except Exception as e:
                logger.warning(
                    "Failed to load Mind state from database (%s); using empty lists", e
                )
                self._resources = []
                self._roles = []
                self._loaded = True

    # ID: f401ea0f-3702-4839-9696-0cb0b74d5be7
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
            "Orchestrator: Selected resource '%s' for role '%s'",
            resource.name,
            role_name,
        )

        # ID: 2a87a79b-31b2-4781-bc20-61edb061f044
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

        Constitutional Note:
        Uses cached ConfigService loaded during initialize().
        No session creation - config was loaded via MindStateService.
        """
        prefix = (resource.env_prefix or "").strip().upper()
        if not prefix:
            raise ValueError(
                f"Resource '{resource.name}' is missing env_prefix (Mind misconfiguration)"
            )

        # Use cached config service (loaded during initialize)
        if self._config_service is None:
            raise RuntimeError("ConfigService not loaded. Call initialize() first.")

        config = self._config_service

        api_url = await config.get(f"{prefix}_API_URL")
        if not api_url:
            raise ValueError(
                f"Configuration '{prefix}_API_URL' is missing from the Database. Run 'poetry run core-admin manage dotenv sync --write' to populate runtime settings from your .env file."
            )
        model_name = await config.get(f"{prefix}_MODEL_NAME")
        if not model_name:
            raise ValueError(
                f"Configuration '{prefix}_MODEL_NAME' is missing from the Database. Run 'poetry run core-admin manage dotenv sync --write'."
            )
        api_key = None
        try:
            api_key = await config.get_secret(
                f"{prefix}_API_KEY",
                audit_context=f"client_orchestrator:{resource.name}",
            )
        except KeyError:
            pass

        if "anthropic" in api_url.lower():
            logger.info("Creating AnthropicProvider for %s", resource.name)
            from shared.infrastructure.llm.providers.anthropic import AnthropicProvider

            return AnthropicProvider(
                api_url=api_url, model_name=model_name, api_key=api_key
            )
        if "ollama" in resource.name.lower() or "11434" in api_url:
            logger.info("Creating OllamaProvider for %s", resource.name)
            return OllamaProvider(
                api_url=api_url, model_name=model_name, api_key=api_key
            )
        logger.info("Creating OpenAIProvider for %s", resource.name)
        return OpenAIProvider(api_url=api_url, model_name=model_name, api_key=api_key)

    # ID: 63a49187-d85e-4f35-beda-491ed4f9810b
    def get_cached_resource_names(self) -> list[str]:
        """Get list of currently cached resource names."""
        return self._client_registry.get_cached_resource_names()

    # ID: f58fc05c-b73f-4a00-995c-40c5f526bc83
    async def clear_cache(self) -> None:
        """Clear all cached clients."""
        logger.info("Orchestrator: Clearing client cache")
        self._client_registry.clear_cache()


# Constitutional Note:
# This is the constitutional pattern: Mind/Body/Will separation enforced via types.
# MindStateService is required, not optional. Callers must provide it.
# ConfigService is loaded once and cached - no repeated session creation.
# No get_session imports anywhere - pure dependency injection.
