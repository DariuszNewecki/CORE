# src/body/services/mind_state_service.py

"""
MindStateService - Body layer service for accessing Mind state.

Constitutional Compliance:
- Body layer service: Provides capability without making decisions
- Mind/Body/Will separation: Encapsulates Mind state access
- No direct database access in Will: Will gets Mind state through this service
- Dependency injection: Takes AsyncSession, no global imports

Part of Mind-Body-Will architecture:
- Mind: Database contains LlmResource, CognitiveRole, Config (what is available)
- Body: This service provides access to Mind state (capability)
- Will: Uses this service to load Mind state for decision-making (strategy)
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.config_service import ConfigService
from shared.infrastructure.database.models import CognitiveRole, LlmResource
from shared.logger import getLogger


logger = getLogger(__name__)

__all__ = ["MindStateService"]


# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
class MindStateService:
    """
    Body service for accessing Mind state (LlmResources, CognitiveRoles, Config).

    Responsibilities:
    - Provide read access to Mind state from database
    - Encapsulate database queries for Mind data
    - Return structured data for Will to make decisions

    Does NOT:
    - Make decisions about which resource to use (that's Will)
    - Modify Mind state (Mind is read-only to Body/Will)
    - Manage LLM client lifecycle (that's ClientRegistry)
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize service with database session.

        Args:
            session: Active database session for queries
        """
        self.session = session

    # ID: b2c3d4e5-f678-90ab-cdef-1234567890ab
    async def get_llm_resources(self) -> list[LlmResource]:
        """
        Retrieve all configured LLM resources from Mind.

        Returns:
            List of LlmResource model instances

        Constitutional Note:
        Mind state is read-only. This method provides access without modification.
        """
        stmt = select(LlmResource)
        result = await self.session.execute(stmt)
        resources = list(result.scalars().all())

        logger.debug("Retrieved %d LLM resources from Mind", len(resources))
        return resources

    # ID: c3d4e5f6-7890-abcd-ef12-34567890abcd
    async def get_cognitive_roles(self) -> list[CognitiveRole]:
        """
        Retrieve all configured cognitive roles from Mind.

        Returns:
            List of CognitiveRole model instances

        Constitutional Note:
        Cognitive roles define how agents should behave. This is Mind's domain.
        Body provides access; Will decides which role to use.
        """
        stmt = select(CognitiveRole)
        result = await self.session.execute(stmt)
        roles = list(result.scalars().all())

        logger.debug("Retrieved %d cognitive roles from Mind", len(roles))
        return roles

    # ID: d4e5f678-90ab-cdef-1234-567890abcdef
    async def get_config_service(self) -> ConfigService:
        """
        Create and return a ConfigService instance for configuration access.

        Returns:
            Initialized ConfigService with preloaded cache

        Constitutional Note:
        ConfigService handles both database config and secrets.
        This method provides the service; callers use it to get specific values.
        """
        config_service = await ConfigService.create(self.session)

        logger.debug(
            "Created ConfigService with %d cached values",
            len(config_service._cache),
        )
        return config_service

    # ID: e5f67890-abcd-ef12-3456-7890abcdef12
    async def load_mind_state(
        self,
    ) -> tuple[list[LlmResource], list[CognitiveRole], ConfigService]:
        """
        Load complete Mind state in one call (convenience method).

        Returns:
            Tuple of (llm_resources, cognitive_roles, config_service)

        Constitutional Note:
        This is a convenience wrapper that loads all Mind state components.
        Useful for initialization where Will needs complete Mind context.

        Example:
            resources, roles, config = await mind_service.load_mind_state()
        """
        resources = await self.get_llm_resources()
        roles = await self.get_cognitive_roles()
        config = await self.get_config_service()

        logger.info(
            "Loaded Mind state: %d resources, %d roles, %d config values",
            len(resources),
            len(roles),
            len(config._cache),
        )

        return resources, roles, config


# Constitutional Note:
# This service exists because Will layer MUST NOT import get_session directly.
# Will depends on Body for capabilities. This service IS that capability.
# Any Will component needing Mind state should receive MindStateService via DI.
