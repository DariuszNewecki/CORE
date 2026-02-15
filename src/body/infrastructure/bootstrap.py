# src/body/infrastructure/bootstrap.py
# ID: 9a8b7c6d-5e4f-3d2e-1c0b-9a8f7e6d5c4b

"""
System Bootstrap - CoreContext Initialization

CONSTITUTIONAL FIX:
Updated _build_context_service to use the ServiceRegistry.
This prevents the 'Two Brains' bug where the ContextService would
create its own private, uninitialized CognitiveService.
"""

from __future__ import annotations

from body.atomic.executor import ActionExecutor
from shared.config import settings
from shared.context import CoreContext
from shared.infrastructure.context.service import ContextService
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.git_service import GitService
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.infrastructure.storage.file_handler import FileHandler
from shared.models import PlannerConfig
from shared.path_resolver import PathResolver


def _build_context_service() -> ContextService:
    """
    Factory for ContextService.

    CONSTITUTIONAL FIX:
    We no longer instantiate QdrantService or CognitiveService here.
    Instead, we pass None, and the ContextService (updated in Step 9)
     will pull the initialized versions from the registry JIT.
    """
    from body.services.service_registry import service_registry

    return ContextService(
        project_root=str(settings.REPO_PATH),
        session_factory=service_registry.session,  # Use the global session factory
        qdrant_client=None,  # Will be resolved from registry
        cognitive_service=None,  # Will be resolved from registry
    )


# ID: 140caea1-4d7b-4b80-ad31-80d0d2dc2a90
def create_core_context(service_registry) -> CoreContext:
    """
    Bootstrap CoreContext and prime the ServiceRegistry.
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

    # 3. Create PathResolver (The Map)
    path_resolver = PathResolver.from_repo(
        repo_root=repo_path, intent_root=settings.MIND
    )

    # 4. Build the Context object
    core_context = CoreContext(
        registry=service_registry,
        git_service=GitService(repo_path),
        file_handler=FileHandler(str(repo_path)),
        planner_config=PlannerConfig(),
        knowledge_service=KnowledgeService(repo_path),
    )

    # 5. HEALED WIRING: Attach Resolver and Executor
    core_context.path_resolver = path_resolver
    core_context.action_executor = ActionExecutor(core_context)

    # 6. Attach the factory
    core_context.context_service_factory = _build_context_service

    return core_context
