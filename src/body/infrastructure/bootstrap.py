# src/body/infrastructure/bootstrap.py

"""
System Bootstrap - CoreContext Initialization

CONSTITUTIONAL EXEMPTION:
This module is the 'Ignition Point'. It IS the infrastructure layer.
It MUST import 'settings' directly to wire the Dependency Injection container.
Once CoreContext is created here, all other layers receive configuration
via DI, complying with the constitution.
"""

from __future__ import annotations

from body.atomic.executor import ActionExecutor
from body.services.file_service import FileService
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
        session_factory=service_registry.session,
        qdrant_client=None,
        cognitive_service=None,
        brain_services_provider=service_registry,
    )


def _build_context_builder_factory(core_context: CoreContext):
    """
    Factory-of-factories for ArchitecturalContextBuilder. ADR-025.

    Returns a zero-arg closure that, when called by CoreContext.context_builder,
    reads cognitive_service and qdrant_service from the supplied core_context
    and assembles a fully-wired ArchitecturalContextBuilder. Both services
    must be populated on core_context by the time the closure is invoked
    (the daemon lifespan does this; CLI commands that need Priority 1 mode
    must do the same). Missing deps surface as a non-RuntimeError exception
    so action_build_tests' JIT-fallback can catch and proceed with None.
    """

    def _factory():
        from will.tools.architectural_context_builder import (
            ArchitecturalContextBuilder,
        )
        from will.tools.module_anchor_generator import ModuleAnchorGenerator
        from will.tools.policy_vectorizer import PolicyVectorizer

        cognitive = core_context.cognitive_service
        qdrant = core_context.qdrant_service
        if cognitive is None or qdrant is None:
            raise ValueError(
                "context_builder factory requires cognitive_service and "
                "qdrant_service to be populated on CoreContext; got "
                f"cognitive_service={cognitive!r}, qdrant_service={qdrant!r}",
            )

        repo_root = settings.REPO_PATH
        builder_path_resolver = PathResolver.from_repo(
            repo_root=repo_root,
            intent_root=settings.MIND,
        )
        return ArchitecturalContextBuilder(
            policy_vectorizer=PolicyVectorizer(repo_root, cognitive, qdrant),
            anchor_generator=ModuleAnchorGenerator(repo_root, cognitive, qdrant),
            path_resolver=builder_path_resolver,
            session_factory=core_context.registry.session,
            cognitive_service=cognitive,
            qdrant_service=qdrant,
        )

    return _factory


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
        repo_root=repo_path,
        intent_root=settings.MIND,
    )

    # 4. Build the Context object
    core_context = CoreContext(
        registry=service_registry,
        settings=settings,
        git_service=GitService(repo_path),
        file_handler=FileHandler(str(repo_path)),
        file_service=FileService(repo_path),
        planner_config=PlannerConfig(),
        knowledge_service=KnowledgeService(repo_path),
    )

    # 5. Attach Resolver and Executor
    core_context.path_resolver = path_resolver
    core_context.action_executor = ActionExecutor(core_context)

    # 6. Attach the factories
    core_context.context_service_factory = _build_context_service
    # ADR-025
    core_context.context_builder_factory = _build_context_builder_factory(core_context)

    return core_context
