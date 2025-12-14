# src/will/agents/cognitive_orchestrator.py

"""
Will: Makes decisions about which LLM resources to use for which roles.
Uses Body components but doesn't manage their lifecycle.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from shared.infrastructure.database.models import CognitiveRole, LlmResource
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.llm.client import LLMClient
from shared.infrastructure.llm.client_registry import LLMClientRegistry
from shared.logger import getLogger
from will.agents.resource_selector import ResourceSelector


logger = getLogger(__name__)


# ID: 68d48c41-09f8-449a-9a28-1d9a3d20101e
class CognitiveOrchestrator:
    """
    Will: Decides which resource to use for which role.
    Delegates client management to registry (Body).
    """

    def __init__(self, repo_path: Path):
        self._repo_path = Path(repo_path)
        self._resources: list[LlmResource] = []
        self._roles: list[CognitiveRole] = []
        self._client_registry = LLMClientRegistry()
        self._loaded = False

    # ID: 18a2986d-296b-4388-b2b1-8796d85b5ee2
    async def initialize(self) -> None:
        """Load Mind (roles and resources from DB)."""
        if self._loaded:
            return
        logger.info("CognitiveOrchestrator: Loading roles and resources from Mind...")
        async with get_session() as session:
            res_result = await session.execute(select(LlmResource))
            role_result = await session.execute(select(CognitiveRole))
            self._resources = list(res_result.scalars().all())
            self._roles = list(role_result.scalars().all())
        self._loaded = True
        logger.info(
            "Loaded %s resources, %s roles", len(self._resources), len(self._roles)
        )

    # ID: a16f98de-17d6-4787-9d94-ab4bf63bc96f
    async def get_client_for_role(self, role_name: str) -> LLMClient:
        """
        Will: Decide which resource to use, then get client from registry.
        """
        if not self._loaded:
            await self.initialize()
        resource = ResourceSelector.select_resource_for_role(
            role_name, self._roles, self._resources
        )
        if not resource:
            raise RuntimeError(f"No resource found for role '{role_name}'")
        from will.orchestration.cognitive_service import CognitiveService

        # ID: aec81806-c12d-4f9c-9ca0-d159f3c124ff
        def provider_factory(r):
            return CognitiveService._create_provider_for_resource_static(r)

        return await self._client_registry.get_or_create_client(
            resource, provider_factory
        )
