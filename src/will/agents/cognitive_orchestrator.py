# src/will/agents/cognitive_orchestrator.py

"""
CognitiveOrchestrator - Will layer orchestrator for LLM client selection.

Constitutional Compliance:
- Will layer: Makes decisions about which resource to use
- Mind/Body/Will separation: Uses MindStateService (Body) for Mind state access
- No direct database access
- No imports back into Will orchestration services (provider factory is injected)

Part of Mind-Body-Will architecture:
- Mind: Database contains LlmResource, CognitiveRole definitions
- Body: MindStateService provides access, ClientRegistry manages clients
- Will: This orchestrator decides which resource to use for which role
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from body.services.mind_state_service import MindStateService
from shared.infrastructure.database.models import CognitiveRole, LlmResource
from shared.infrastructure.llm.client import LLMClient
from shared.infrastructure.llm.client_registry import LLMClientRegistry
from shared.logger import getLogger
from will.agents.resource_selector import ResourceSelector


logger = getLogger(__name__)

ProviderFactory = Callable[
    [LlmResource], Awaitable[object]
]  # AIProvider, but keep loose


# ID: 68d48c41-09f8-449a-9a28-1d9a3d20101e
class CognitiveOrchestrator:
    """
    Will: Decides which resource to use for which role.
    Delegates client management to registry (Body).

    Constitutional Note:
    - Requires MindStateService via dependency injection.
    - Provider creation is injected (no back-imports).
    """

    def __init__(
        self,
        repo_path: Path,
        mind_state_service: MindStateService,
        provider_factory: ProviderFactory,
    ):
        self._repo_path = Path(repo_path)
        self._resources: list[LlmResource] = []
        self._roles: list[CognitiveRole] = []
        self._client_registry = LLMClientRegistry()
        self._loaded = False
        self._mind_state_service = mind_state_service
        self._provider_factory = provider_factory

    # ID: 18a2986d-296b-4388-b2b1-8796d85b5ee2
    async def initialize(self) -> None:
        """Load Mind (roles and resources) using MindStateService (Body)."""
        if self._loaded:
            return

        logger.info("CognitiveOrchestrator: Loading roles and resources from Mind...")
        self._resources = await self._mind_state_service.get_llm_resources()
        self._roles = await self._mind_state_service.get_cognitive_roles()

        self._loaded = True
        logger.info(
            "Loaded %s resources, %s roles", len(self._resources), len(self._roles)
        )

    # ID: a16f98de-17d6-4787-9d94-ab4bf63bc96f
    async def get_client_for_role(self, role_name: str) -> LLMClient:
        """Will: choose resource, then obtain client from registry (Body)."""
        if not self._loaded:
            await self.initialize()

        resource = ResourceSelector.select_resource_for_role(
            role_name, self._roles, self._resources
        )
        if not resource:
            raise RuntimeError(f"No resource found for role '{role_name}'")

        return await self._client_registry.get_or_create_client(
            resource, self._provider_factory
        )
