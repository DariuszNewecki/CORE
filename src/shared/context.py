# src/shared/context.py

"""
Defines the CoreContext, a dataclass that holds singleton instances of all major
services, enabling explicit dependency injection throughout the application.

ALIGNED: Added file_content_cache to support A2/A3 cross-step context persistence.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from shared.config import settings


if TYPE_CHECKING:
    from body.infrastructure.storage.file_handler import FileHandler
    from body.services.file_service import FileService
    from mind.governance.audit_context import AuditorContext
    from shared.infrastructure.clients.qdrant_client import QdrantService
    from shared.infrastructure.git_service import GitService
    from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
    from shared.models.execution_models import PlannerConfig
    from shared.path_resolver import PathResolver
    from shared.protocols.executor import ActionExecutorProtocol
    from will.orchestration.cognitive_service import CognitiveService


@dataclass
# ID: 2fb7b7db-7dff-432b-b99a-cebe0707d33a
class CoreContext:
    """
    A container for shared services, passed explicitly to commands.

    ADR-128 three-tier model:
    - Mandatory fields (git_service, knowledge_service, file_handler, file_service):
      required at construction; missing one raises TypeError immediately.
    - Post-construction infrastructure (path_resolver, action_executor):
      Optional, set by bootstrap immediately after construction; remain None
      in bare construction paths (daemon, alignment persistence).
    - Genuinely-degradable services (cognitive_service, auditor_context,
      qdrant_service, planner_config): Optional; daemon wires them in try/except
      so the runtime degrades gracefully when LLM / Qdrant / audit is unavailable.
    """

    # The authoritative registry
    registry: Any

    # --- Always-wired services (#643) ---
    # These are guaranteed at construction by every production path (bootstrap,
    # daemon) and are therefore non-Optional. A construction site that forgets
    # one fails fast rather than handing consumers a None that hundreds of call
    # sites assume is present. Contrast the genuinely-degradable services below,
    # which stay Optional (the daemon wires them in try/except).
    git_service: GitService
    knowledge_service: KnowledgeService
    file_handler: FileHandler
    # ADR-097 D4 Will-tier write door: the sanctioned FileService wrapper so
    # Will-tier consumers receive it (not a raw FileHandler) for `file_service:
    # FileService` slots. file_handler stays for Body/infra consumers (#645).
    file_service: FileService

    # --- Configuration SSOT ---
    # FIXED: Uses default_factory to avoid "mutable default" ValueError
    settings: Any = field(default_factory=lambda: settings)

    # --- Active Service Instances (genuinely optional / JIT-injected) ---
    # ADR-128: typed Optional rather than Any | None so attribute access is
    # checked by mypy; callers guard with `if ctx.x is not None` before use.
    cognitive_service: CognitiveService | None = None
    auditor_context: AuditorContext | None = None
    planner_config: PlannerConfig | None = None
    qdrant_service: QdrantService | None = None
    debug: bool = False
    verbose: bool = False

    # --- Post-construction infrastructure (ADR-128 D2) ---
    # Set immediately after CoreContext() in bootstrap; None only in bare
    # construction paths (daemon, alignment persistence) that don't need them.
    path_resolver: PathResolver | None = field(default=None)
    action_executor: ActionExecutorProtocol | None = field(default=None)

    # ALIGNED: Shared state for autonomous agents to pass file content between plan steps
    file_content_cache: dict[str, str] = field(default_factory=dict)

    _is_test_mode: bool = False

    # Factory used to create a ContextService instance.
    context_service_factory: Callable[[], Any] | None = field(
        default=None,
        repr=False,
    )

    _context_service: Any = field(default=None, init=False, repr=False)

    # ADR-025: factory used to create an ArchitecturalContextBuilder instance.
    # Mirrors the context_service_factory triple — wired at the bootstrap
    # factory site so CoderAgent reaches Priority 1 ("Semantic Architectural
    # Context") prompt mode for build.tests and any other consumer.
    context_builder_factory: Callable[[], Any] | None = field(
        default=None,
        repr=False,
    )

    _context_builder: Any = field(default=None, init=False, repr=False)

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

    @property
    # ID: 6b8a7ca6-2c75-4072-ba2b-3e1708b5f9bf
    def context_builder(self) -> Any:
        """
        Get or create ArchitecturalContextBuilder instance. ADR-025.
        """
        if self._context_builder is None:
            if self.context_builder_factory is None:
                raise RuntimeError(
                    "ArchitecturalContextBuilder factory is not configured on "
                    "CoreContext. This should be wired in the composition root "
                    "(CLI/API).",
                )
            self._context_builder = self.context_builder_factory()

        return self._context_builder
