# src/body/infrastructure/bootstrap.py
# ID: 9a8b7c6d-5e4f-3d2e-1c0b-9a8f7e6d5c4b

"""
System Bootstrap - CoreContext Initialization

Constitutional Purpose:
This infrastructure module is the ONLY place that reads settings
to construct CoreContext for the CLI and API. It exists in the
infrastructure layer where settings access and database primitives
are constitutionally permitted.
"""

from __future__ import annotations

from body.atomic.executor import ActionExecutor  # ADDED: Concrete implementation
from shared.config import settings
from shared.context import CoreContext
from shared.infrastructure.context.service import ContextService
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.git_service import GitService
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.infrastructure.storage.file_handler import FileHandler
from shared.models import PlannerConfig


def _build_context_service() -> ContextService:
    """
    Factory for ContextService, wired for the internal substrate.
    Moved from api/main.py to comply with logic.di.no_global_session.
    """
    return ContextService(
        project_root=str(settings.REPO_PATH),
        session_factory=get_session,
    )


# ID: 9a8b7c6d-5e4f-3d2e-1c0b-9a8f7e6d5c4b
def create_core_context(service_registry) -> CoreContext:
    """
    Bootstrap CoreContext and prime the ServiceRegistry.

    PRESERVED FEATURES:
    - Registry Priming with get_session.
    - Full initialization of Git, File, and Knowledge services.
    - ContextService factory wiring.
    """
    # 1. Prime the registry with the database primitive
    service_registry.prime(get_session)

    # 2. Configure infrastructure connections
    service_registry.configure(
        repo_path=settings.REPO_PATH,
        qdrant_url=settings.QDRANT_URL,
        qdrant_collection_name=settings.QDRANT_COLLECTION_NAME,
    )

    repo_path = settings.REPO_PATH

    # 3. Build the Context object
    core_context = CoreContext(
        registry=service_registry,
        git_service=GitService(repo_path),
        file_handler=FileHandler(str(repo_path)),
        planner_config=PlannerConfig(),
        knowledge_service=KnowledgeService(repo_path),
    )

    # 4. HEALED WIRING: Instantiate the universal mutation gateway
    # This marries the Body (Executor) to the Context.
    core_context.action_executor = ActionExecutor(core_context)

    # 5. Attach the factory (now internal to this module)
    core_context.context_service_factory = _build_context_service

    return core_context
