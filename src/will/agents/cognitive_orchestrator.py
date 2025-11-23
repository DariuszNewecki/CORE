# src/will/agents/cognitive_orchestrator.py

"""
Will: Makes decisions about which LLM resources to use for which roles.
Uses Body components but doesn't manage their lifecycle.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from services.database.models import CognitiveRole, LlmResource
from services.database.session_manager import get_session
from services.llm.client import LLMClient
from services.llm.client_registry import LLMClientRegistry
from shared.logger import getLogger
from will.agents.resource_selector import ResourceSelector

logger = getLogger(__name__)


# ID: 2fb8d9cc-689c-4c94-bf33-ccdbfa32e3e7
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

    # ID: 8e126b7b-e30d-4747-a30e-ca1577228b7e
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
            f"Loaded {len(self._resources)} resources, {len(self._roles)} roles"
        )

    # ID: 939dcb1b-26d8-4de9-bf51-148f575e0ed7
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

        # ID: 2933e250-250a-4bb8-ba46-c3badc55211e
        def provider_factory(r):
            return CognitiveService._create_provider_for_resource_static(r)

        return await self._client_registry.get_or_create_client(
            resource, provider_factory
        )
