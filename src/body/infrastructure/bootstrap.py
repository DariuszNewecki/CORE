# src/body/infrastructure/bootstrap.py
"""
System Bootstrap - CoreContext Initialization

Constitutional Purpose:
This infrastructure module is the ONLY place that reads settings
to construct CoreContext for the CLI. It exists in the infrastructure
layer where settings access is constitutionally permitted.

All CLI commands receive the bootstrapped context and never access settings.
"""

from __future__ import annotations

from shared.config import settings
from shared.context import CoreContext
from shared.infrastructure.context.service import ContextService
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.git_service import GitService
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.infrastructure.storage.file_handler import FileHandler
from shared.models import PlannerConfig


# ID: 9a8b7c6d-5e4f-3d2e-1c0b-9a8f7e6d5c4b
def create_core_context(service_registry) -> CoreContext:
    """
    Bootstrap CoreContext from settings.

    Constitutional Boundary:
    This function exists in infrastructure layer where settings access is permitted.
    It reads configuration and constructs CoreContext for CLI commands.

    Args:
        service_registry: The service registry to inject into context

    Returns:
        Fully initialized CoreContext ready for command execution
    """
    service_registry.configure(
        repo_path=settings.REPO_PATH,
        qdrant_url=settings.QDRANT_URL,
        qdrant_collection_name=settings.QDRANT_COLLECTION_NAME,
    )
    repo_path = settings.REPO_PATH

    context = CoreContext(
        registry=service_registry,
        git_service=GitService(repo_path),
        file_handler=FileHandler(str(repo_path)),
        planner_config=PlannerConfig(),
        cognitive_service=None,  # Lazy-loaded via registry when needed
        knowledge_service=KnowledgeService(repo_path),
        qdrant_service=None,  # Lazy-loaded via registry when needed
        auditor_context=None,  # Lazy-loaded when governance commands run
    )

    # Factory for ContextService (also needs repo_path)
    def _build_context_service() -> ContextService:
        return ContextService(
            qdrant_client=None,
            cognitive_service=None,
            config={},
            project_root=str(repo_path),
            session_factory=get_session,
            service_registry=service_registry,
        )

    context.context_service_factory = _build_context_service

    return context
