# src/shared/context.py
"""
Defines the CoreContext, a dataclass that holds singleton instances of all major
services, enabling explicit dependency injection throughout the application.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
# ID: 9f1dd7c7-1cb2-435d-bd07-b7d436c9459f
class CoreContext:
    """
    A container for shared services, passed explicitly to commands.

    Refactored for A2 Autonomy: Now relies on ServiceRegistry for
    infrastructure instantiation to prevent split-brain states.
    """

    # These fields are kept for backwards compatibility with existing commands
    # until they can be migrated to use the registry.
    git_service: Any
    cognitive_service: Any
    knowledge_service: Any
    auditor_context: Any
    file_handler: Any
    planner_config: Any

    # The authoritative registry (added for the refactor)
    registry: Any | None = None

    # Optional direct reference to Qdrant (managed via registry now)
    qdrant_service: Any | None = None

    _is_test_mode: bool = False

    # Factory used to create a ContextService instance.
    context_service_factory: Callable[[], Any] | None = field(
        default=None,
        repr=False,
    )

    _context_service: Any = field(default=None, init=False, repr=False)

    @property
    # ID: 11a1768b-d222-40af-99d7-0d45d300e2ba
    def context_service(self) -> Any:
        """
        Get or create ContextService instance.

        Provides constitutional governance for all LLM context via ContextPackages.
        """
        if self._context_service is None:
            if self.context_service_factory is None:
                raise RuntimeError(
                    "ContextService factory is not configured on CoreContext. "
                    "This should be wired in the composition root (CLI/API).",
                )
            self._context_service = self.context_service_factory()

        return self._context_service
