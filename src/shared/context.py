# src/shared/context.py
# ID: 9f1dd7c7-1cb2-435d-bd07-b7d436c9459f

"""
Defines the CoreContext, a dataclass that holds singleton instances of all major
services, enabling explicit dependency injection throughout the application.

ALIGNED: Added file_content_cache to support A2/A3 cross-step context persistence.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from shared.config import settings


@dataclass
# ID: 2fb7b7db-7dff-432b-b99a-cebe0707d33a
class CoreContext:
    """
    A container for shared services, passed explicitly to commands.

    ARCHITECTURAL NOTE:
    The 'registry' field is the authoritative source for services.
    Direct service fields (git_service, etc.) are populated via JIT
    injection in the CLI/API lifecycle.
    """

    # The authoritative registry
    registry: Any

    # --- Active Service Instances ---
    git_service: Any | None = None
    cognitive_service: Any | None = None
    knowledge_service: Any | None = None
    auditor_context: Any | None = None
    file_handler: Any | None = None
    planner_config: Any | None = None
    qdrant_service: Any | None = None

    # ALIGNED: Shared state for autonomous agents to pass file content between plan steps
    file_content_cache: dict[str, str] = field(default_factory=dict)

    _is_test_mode: bool = False

    # Factory used to create a ContextService instance.
    context_service_factory: Callable[[], Any] | None = field(
        default=None,
        repr=False,
    )

    _context_service: Any = field(default=None, init=False, repr=False)

    @property
    # ID: 04a360f4-085c-4e48-a6df-b908fcf40520
    def db_available(self) -> bool:
        """
        Constitutional health check for the database.
        Returns True if a database URL is configured.
        """
        return bool(settings.DATABASE_URL)

    @property
    # ID: 11a1768b-d222-40af-99d7-0d45d300e2ba
    def context_service(self) -> Any:
        """
        Get or create ContextService instance.
        """
        if self._context_service is None:
            if self.context_service_factory is None:
                raise RuntimeError(
                    "ContextService factory is not configured on CoreContext. "
                    "This should be wired in the composition root (CLI/API).",
                )
            self._context_service = self.context_service_factory()

        return self._context_service
