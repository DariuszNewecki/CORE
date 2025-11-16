# src/shared/context.py
"""
Defines the CoreContext, a dataclass that holds singleton instances of all major
services, enabling explicit dependency injection throughout the application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.services.context import ContextService


@dataclass
# ID: 9f1dd7c7-1cb2-435d-bd07-b7d436c9459f
class CoreContext:
    """
    A container for shared services, passed explicitly to commands.

    NOTE: Fields are typed as 'Any' to avoid cross-domain imports from here.
    Concrete types are created/wired in the CLI layer.
    """

    git_service: Any
    cognitive_service: Any
    knowledge_service: Any
    qdrant_service: Any
    auditor_context: Any
    file_handler: Any
    planner_config: Any
    _is_test_mode: bool = False
    _context_service: Any = field(default=None, init=False, repr=False)

    @property
    # ID: 11a1768b-d222-40af-99d7-0d45d300e2ba
    def context_service(self) -> ContextService:
        """
        Get or create ContextService instance.

        Provides constitutional governance for all LLM context via ContextPackages.
        """
        if self._context_service is None:
            from src.services.context import ContextService
            from src.shared.config import settings

            # Initialize with existing services
            self._context_service = ContextService(
                db_service=None,  # TODO: Wire when DB service available
                qdrant_client=self.qdrant_service,
                cognitive_service=self.cognitive_service,
                config={},
                project_root=str(settings.REPO_PATH),
            )

        return self._context_service
