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
import os
from pathlib import Path

from services.config_service import config_service
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

    # ID: afff714a-8e04-4c35-97c7-11bda8507c92
    async def initialize(self) -> None:
        """
        Load Mind state: Read roles and resources from database.

        This is the orchestrator's connection to the Mind - it reads
        the constitutional rules about what roles exist and what resources
        are available to fulfill them.
        """
        async with self._init_lock:
            if self._loaded:
                return
            try:
                logger.info("ClientOrchestrator: Loading Mind state from database...")
                async with get_session() as session:
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

        This is the core orchestration method that:
        1. Ensures Mind state is loaded
        2. Decides which resource should handle this role (Mind rules)
        3. Delegates to Body to get/create the actual client

        Args:
            role_name: Name of cognitive role (e.g., "Coder", "Planner")

        Returns:
            Configured LLMClient ready to use

        Raises:
            RuntimeError: If no suitable resource found or client creation fails
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
        logger.info(
            f"Orchestrator: Selected resource '{resource.name}' for role '{role_name}'"
        )

        # ID: fd5528a7-7e30-47af-9741-ca1a17fd555d
        async def provider_factory(res: LlmResource) -> AIProvider:
            return await self._create_provider_for_resource(res)

        try:
            client = await self._client_registry.get_or_create_client(
                resource, provider_factory
            )
            logger.info(
                f"Orchestrator: Successfully provisioned client for role '{role_name}'"
            )
            return client
        except Exception as e:
            raise RuntimeError(
                f"Failed to provision client for role '{role_name}': {e}"
            ) from e

    async def _create_provider_for_resource(self, resource: LlmResource) -> AIProvider:
        """
        Create the correct provider for a resource.

        This is Will's decision-making: choosing which provider implementation
        to use based on resource configuration.

        Args:
            resource: LlmResource from Mind

        Returns:
            Configured AIProvider instance

        Raises:
            ValueError: If resource configuration is invalid
        """
        prefix = (resource.env_prefix or "").strip().upper()
        if not prefix:
            raise ValueError(
                f"Resource '{resource.name}' is missing env_prefix (Mind misconfiguration)"
            )
        api_url = await config_service.get(f"{prefix}_API_URL") or os.getenv(
            f"{prefix}_API_URL"
        )
        model_name = await config_service.get(f"{prefix}_MODEL_NAME") or os.getenv(
            f"{prefix}_MODEL_NAME"
        )
        api_key = None
        try:
            api_key = await config_service.get_secret(
                f"{prefix}_API_KEY",
                audit_context=f"client_orchestrator:{resource.name}",
            )
            logger.debug(f"Retrieved encrypted API key for {resource.name}")
        except KeyError:
            api_key = os.getenv(f"{prefix}_API_KEY")
            if api_key:
                logger.warning(
                    f"Using API key from environment for {resource.name}. Consider migrating: core-admin secrets set {prefix}_API_KEY"
                )
        if not api_url or not model_name:
            raise ValueError(
                f"Missing required config for resource '{resource.name}' with prefix '{prefix}_'. Ensure URL and model_name are configured."
            )
        if "ollama" in resource.name.lower() or "11434" in (api_url or ""):
            logger.info(f"Creating OllamaProvider for {resource.name}")
            return OllamaProvider(
                api_url=api_url, model_name=model_name, api_key=api_key
            )
        logger.info(f"Creating OpenAIProvider for {resource.name}")
        return OpenAIProvider(api_url=api_url, model_name=model_name, api_key=api_key)

    # ID: aae28476-3d3f-428a-a01a-6ae302e119a4
    def get_cached_resource_names(self) -> list[str]:
        """
        Get list of currently cached resource names.

        Useful for debugging and monitoring.

        Returns:
            List of resource names currently in cache
        """
        return self._client_registry.get_cached_resource_names()

    # ID: 1b744485-8a18-46cf-9037-04a0fffa4c9b
    async def clear_cache(self) -> None:
        """
        Clear all cached clients.

        Useful for:
        - Testing
        - Configuration changes requiring fresh clients
        - Resource cleanup

        Note: This is an orchestration decision, but delegates to Body for execution.
        """
        logger.info("Orchestrator: Clearing client cache")
        self._client_registry.clear_cache()
