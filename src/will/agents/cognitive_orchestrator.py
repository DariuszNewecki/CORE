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
from functools import partial
from pathlib import Path
from typing import cast

from body.services.mind_state_service import MindStateService
from shared.infrastructure.database.models import (
    CognitiveRole,
    LlmResource,
    RoleResourceAssignment,
)
from shared.infrastructure.llm.client_registry import LLMClientRegistry
from shared.infrastructure.llm.fallback_client import FallbackAwareLLMClient
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
        self._assignments: list[RoleResourceAssignment] = []
        self._client_registry = LLMClientRegistry()
        self._loaded = False
        self._mind_state_service = mind_state_service
        self._provider_factory = provider_factory
        # ADR-052 principle #6 (#333) / ADR-090 D5: system-level operating_mode
        # loaded from system_config at initialize(); 'local_only' fallback.
        self._system_operating_mode: str = "local_only"

    # ID: 18a2986d-296b-4388-b2b1-8796d85b5ee2
    async def initialize(self) -> None:
        """Load Mind (roles, resources, assignments) using MindStateService (Body)."""
        if self._loaded:
            return

        logger.info("CognitiveOrchestrator: Loading roles and resources from Mind...")
        self._resources = await self._mind_state_service.get_llm_resources()
        self._roles = await self._mind_state_service.get_cognitive_roles()
        # ADR-052 Phase 3: role→resource override now lives in
        # role_resource_assignments, not cognitive_roles.assigned_resource.
        self._assignments = (
            await self._mind_state_service.get_role_resource_assignments()
        )
        # ADR-052 principle #6 (#333) / ADR-090 D5: system-level operating_mode
        # only; per-role override removed (operating_mode is Resource-layer).
        system_config = await self._mind_state_service.get_system_config()
        if system_config is None:
            logger.warning(
                "CognitiveOrchestrator: system_config row missing — "
                "defaulting operating_mode to '%s'",
                self._system_operating_mode,
            )
        else:
            self._system_operating_mode = system_config.operating_mode

        self._loaded = True
        logger.info(
            "Loaded %s resources, %s roles, %s assignments, operating_mode='%s'",
            len(self._resources),
            len(self._roles),
            len(self._assignments),
            self._system_operating_mode,
        )

    # ID: a16f98de-17d6-4787-9d94-ab4bf63bc96f
    async def get_client_for_role(
        self, role_name: str, high_reasoning: bool = False
    ) -> FallbackAwareLLMClient:
        """
        Will: choose qualified resources, then return a fallback-aware
        wrapper that constructs each client lazily through the registry
        (Body) only when the call actually reaches that position.

        Per #293: the wrapper transparently fails over on quota/billing
        statuses (402, 429). Per the #293 follow-up: it also fails over
        on per-resource provisioning errors (ValueError from missing
        config) so one misconfigured row in ``llm_resources`` cannot
        poison an entire role.

        Per #333: ``system_operating_mode`` is threaded through to
        ``ResourceSelector`` so resources whose ``locality`` is barred
        by the effective operating mode are dropped before the fallback
        chain is constructed.
        """
        if not self._loaded:
            await self.initialize()

        ordered = ResourceSelector.select_resources_for_role(
            role_name,
            self._roles,
            self._resources,
            self._assignments,
            system_operating_mode=self._system_operating_mode,
            high_reasoning=high_reasoning,
        )
        if not ordered:
            raise RuntimeError(f"No resource found for role '{role_name}'")

        factories = [
            partial(
                self._client_registry.get_or_create_client,
                resource,
                self._provider_factory,
            )
            for resource in ordered
        ]

        from shared.infrastructure.llm.client import LLMClient

        return FallbackAwareLLMClient(
            client_factories=cast(list[Callable[[], Awaitable[LLMClient]]], factories),
            resource_names=[r.name for r in ordered],
        )
