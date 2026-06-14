# src/will/self_healing/alignment/persistence.py

"""Refactored logic for src/features/self_healing/alignment/persistence.py."""

from __future__ import annotations

from typing import Any

from body.services.service_registry import service_registry
from shared.logger import getLogger
from shared.models.action_result import ActionResult


logger = getLogger(__name__)


# ID: b1dd725e-af8c-43f4-b8f2-d91876672be6
async def update_system_memory(file_path: str, write: bool):
    """Ensures the State (DB) and Mind (Vectors) match the Body (Code)."""
    from body.introspection.sync_service import run_sync_with_db
    from body.introspection.vectorization_service import run_vectorize
    from shared.context import CoreContext
    from shared.infrastructure.bootstrap_registry import BootstrapRegistry
    from shared.infrastructure.git_service import GitService
    from shared.infrastructure.knowledge.knowledge_service import KnowledgeService

    async with service_registry.session() as session:
        await run_sync_with_db(session)
        # git_service / knowledge_service / file_handler are mandatory on
        # CoreContext (#643); wire them so the context is fully constructed.
        repo_path = BootstrapRegistry.get_repo_path()
        ctx = CoreContext(
            registry=service_registry,
            git_service=GitService(repo_path=repo_path),
            knowledge_service=KnowledgeService(repo_path=repo_path),
            file_handler=service_registry.get_file_handler(),
        )
        await run_vectorize(context=ctx, session=session, dry_run=not write)


# ID: 0b46baa7-876a-4579-abd5-49de6bebab3c
async def record_action_result(
    file_path: str,
    ok: bool,
    duration_ms: int,
    error_message: str | None = None,
    action_metadata: dict[str, Any] | None = None,
) -> None:
    """Record alignment action outcome to action_results table."""
    async with service_registry.session() as session:
        result = ActionResult(
            action_type="alignment",
            ok=ok,
            file_path=file_path,
            error_message=error_message,
            action_metadata=action_metadata,
            agent_id="alignment_orchestrator",
            duration_ms=duration_ms,
        )
        session.add(result)
        await session.commit()
    logger.debug(
        "📊 Recorded action_result: alignment %s for %s", "✓" if ok else "✗", file_path
    )
