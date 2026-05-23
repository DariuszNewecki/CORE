# src/body/services/mind_state_service.py

"""
MindStateService - Body layer service for accessing Mind state.

Constitutional Compliance:
- Body layer service: Provides capability without making decisions
- Mind/Body/Will separation: Encapsulates Mind state access
- No direct database access in Will: Will gets Mind state through this service
- Dependency injection: Takes AsyncSession, no global imports

HEALED (V2.3.0):
- Added detach() to explicitly release DB session references.
"""

from __future__ import annotations

from sqlalchemy import select

from body.services.session_attached_service import SessionAttachedService
from shared.infrastructure.config_service import ConfigService
from shared.infrastructure.database.models import (
    CognitiveRole,
    LlmResource,
    RoleResourceAssignment,
    SystemConfig,
)
from shared.logger import getLogger


logger = getLogger(__name__)

__all__ = ["MindStateService"]


# ID: 49fce217-d1fe-480e-8ede-cef3abf4680b
class MindStateService(SessionAttachedService):
    """
    Body service for accessing Mind state (LlmResources, CognitiveRoles, Config).
    """

    # ID: 7d983b1d-83e8-4b07-86a5-f15b7f4ca981
    async def get_llm_resources(self) -> list[LlmResource]:
        """
        Retrieve available LLM resources from Mind.

        Filters ``is_available=false`` rows at fetch time (#333). The
        registry says "do not use" for those rows; the router must not
        see them at all.
        """
        session = self._require_session()

        stmt = select(LlmResource).where(LlmResource.is_available == True)  # noqa: E712
        result = await session.execute(stmt)
        resources = list(result.scalars().all())

        logger.debug("Retrieved %d LLM resources from Mind", len(resources))
        return resources

    # ID: be7cff39-76bc-4ba0-a556-5a336f4a9f0c
    async def get_cognitive_roles(self) -> list[CognitiveRole]:
        """
        Retrieve all configured cognitive roles from Mind.
        """
        session = self._require_session()

        stmt = select(CognitiveRole)
        result = await session.execute(stmt)
        roles = list(result.scalars().all())

        logger.debug("Retrieved %d cognitive roles from Mind", len(roles))
        return roles

    # ID: 0e0c0b7e-67b9-4dcd-bd3a-9f8c4d51a112
    async def get_role_resource_assignments(self) -> list[RoleResourceAssignment]:
        """
        Retrieve role → resource assignments (ADR-052 Phase 3 replacement
        for the dropped ``cognitive_roles.assigned_resource`` column).

        Returns every row; callers filter by ``priority`` and
        ``is_active`` as needed.
        """
        session = self._require_session()

        stmt = select(RoleResourceAssignment)
        result = await session.execute(stmt)
        assignments = list(result.scalars().all())

        logger.debug(
            "Retrieved %d role-resource assignments from Mind", len(assignments)
        )
        return assignments

    # ID: 0bf49f18-ec35-4ba9-aac0-035a8cd18de3
    async def get_system_config(self) -> SystemConfig | None:
        """
        Retrieve the singleton ``system_config`` row (ADR-052).

        Returns ``None`` if no row exists. Used by callers that need the
        system-default ``operating_mode`` (#333).
        """
        session = self._require_session()

        stmt = select(SystemConfig)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    # ID: d4e5f678-90ab-cdef-1234-567890abcdef
    async def get_config_service(self) -> ConfigService:
        """
        Create and return a ConfigService instance for configuration access.
        """
        session = self._require_session()

        config_service = await ConfigService.create(session)
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
