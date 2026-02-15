# src/body/services/mind_state_service.py

"""
MindStateService - Body layer service for accessing Mind state.

Constitutional Compliance:
- Body layer service: Provides capability without making decisions
- Mind/Body/Will separation: Encapsulates Mind state access
- No direct database access in Will: Will gets Mind state through this service
- Dependency injection: Takes AsyncSession, no global imports

HEALED (V2.6.2):
- Added detach() to explicitly release DB session references.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.config_service import ConfigService
from shared.infrastructure.database.models import CognitiveRole, LlmResource
from shared.logger import getLogger


logger = getLogger(__name__)

__all__ = ["MindStateService"]


# ID: 49fce217-d1fe-480e-8ede-cef3abf4680b
class MindStateService:
    """
    Body service for accessing Mind state (LlmResources, CognitiveRoles, Config).
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize service with database session.
        """
        self.session = session

    # ID: 8876c24d-5e6f-4a8b-9c0d-1e2f3a4b5c6d
    def detach(self) -> None:
        """
        Releases the database session reference.
        Prevents the service from holding a connection open after work is done.
        """
        self.session = None

    # ID: 7d983b1d-83e8-4b07-86a5-f15b7f4ca981
    async def get_llm_resources(self) -> list[LlmResource]:
        """
        Retrieve all configured LLM resources from Mind.
        """
        if self.session is None:
            raise RuntimeError("MindStateService error: Session has been detached.")

        stmt = select(LlmResource)
        result = await self.session.execute(stmt)
        resources = list(result.scalars().all())

        logger.debug("Retrieved %d LLM resources from Mind", len(resources))
        return resources

    # ID: be7cff39-76bc-4ba0-a556-5a336f4a9f0c
    async def get_cognitive_roles(self) -> list[CognitiveRole]:
        """
        Retrieve all configured cognitive roles from Mind.
        """
        if self.session is None:
            raise RuntimeError("MindStateService error: Session has been detached.")

        stmt = select(CognitiveRole)
        result = await self.session.execute(stmt)
        roles = list(result.scalars().all())

        logger.debug("Retrieved %d cognitive roles from Mind", len(roles))
        return roles

    # ID: d4e5f678-90ab-cdef-1234-567890abcdef
    async def get_config_service(self) -> ConfigService:
        """
        Create and return a ConfigService instance for configuration access.
        """
        if self.session is None:
            raise RuntimeError("MindStateService error: Session has been detached.")

        config_service = await ConfigService.create(self.session)
        return config_service

    # ID: e5f67890-abcd-ef12-3456-7890abcdef12
    async def load_mind_state(
        self,
    ) -> tuple[list[LlmResource], list[CognitiveRole], ConfigService]:
        """
        Load complete Mind state in one call.
        """
        resources = await self.get_llm_resources()
        roles = await self.get_cognitive_roles()
        config = await self.get_config_service()

        return resources, roles, config
