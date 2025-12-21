# src/body/services/service_registry.py

"""
Provides a centralized, lazily-initialized service registry for CORE.
This acts as the authoritative Dependency Injection container, ensuring
singletons and preventing circular dependencies.
"""

from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy import text

from mind.governance.audit_context import AuditorContext
from shared.config import settings
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.infrastructure.clients.qdrant_client import QdrantService
    from will.orchestration.cognitive_service import CognitiveService
logger = getLogger(__name__)


# ID: fde25013-c11d-4c42-86e2-243ddd3ae10b
class ServiceRegistry:
    """
    A singleton service locator and DI container.
    Manages the lifecycle of infrastructure services to ensure:
    1. Singletons (only one connection pool per service)
    2. Lazy loading (don't import heavy libs until needed)

    DI Pattern: Two-Phase Initialization
    - Phase 1 (inside lock): Construct lightweight objects
    - Phase 2 (outside lock): Initialize async resources
    """

    _instances: ClassVar[dict[str, Any]] = {}
    _service_map: ClassVar[dict[str, str]] = {}
    _initialized: ClassVar[bool] = False
    _init_flags: ClassVar[dict[str, bool]] = {}
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    def __init__(self, repo_path: Path | None = None):
        self.repo_path = repo_path or settings.REPO_PATH

    async def _initialize_from_db(self):
        """Loads the dynamic service map from the database on first access."""
        async with self._lock:
            if self._initialized:
                return
            logger.info("Initializing ServiceRegistry from database...")
            try:
                async with get_session() as session:
                    result = await session.execute(
                        text("SELECT name, implementation FROM core.runtime_services")
                    )
                    for row in result:
                        self._service_map[row.name] = row.implementation
                self._initialized = True
            except Exception as e:
                logger.critical(
                    "Failed to initialize ServiceRegistry from DB: %s", e, exc_info=True
                )
                self._initialized = False

    def _import_class(self, class_path: str):
        """Dynamically imports a class from a string path."""
        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)

    def _ensure_qdrant_instance(self):
        """
        Internal helper to create Qdrant instance if missing.
        MUST be called under lock to ensure safety.
        """
        if "qdrant" not in self._instances:
            logger.debug("Lazy-loading QdrantService...")
            from shared.infrastructure.clients.qdrant_client import QdrantService

            instance = QdrantService(
                url=settings.QDRANT_URL, collection_name=settings.QDRANT_COLLECTION_NAME
            )
            self._instances["qdrant"] = instance
            self._init_flags["qdrant"] = False

    # ID: 8e8fc0c0-11df-4bd8-b365-15c255075d04
    async def get_qdrant_service(self) -> QdrantService:
        """
        Authoritative, lazy, singleton access to Qdrant.
        Prevents 'split-brain' initialization where multiple clients are created.

        Two-Phase Init: Construction (fast) + Initialization (async I/O)
        """
        if "qdrant" not in self._instances:
            async with self._lock:
                self._ensure_qdrant_instance()
            self._init_flags["qdrant"] = True
        return self._instances["qdrant"]

    # ID: e87e3db8-9a2f-4bed-b41e-3ebea0f3b8ef
    async def get_cognitive_service(self) -> CognitiveService:
        """
        Creates CognitiveService, injecting the singleton QdrantService.

        Two-Phase Init: Construction (fast) + Initialization (async I/O)
        """
        if "cognitive_service" not in self._instances:
            async with self._lock:
                if "cognitive_service" not in self._instances:
                    logger.debug("Lazy-loading CognitiveService...")
                    from will.orchestration.cognitive_service import CognitiveService

                    self._ensure_qdrant_instance()
                    qdrant = self._instances["qdrant"]
                    instance = CognitiveService(
                        repo_path=self.repo_path, qdrant_service=qdrant
                    )
                    self._instances["cognitive_service"] = instance
                    self._init_flags["cognitive_service"] = False
            if not self._init_flags.get("cognitive_service"):
                logger.debug("Initializing CognitiveService (loading Mind from DB)...")
                await self._instances["cognitive_service"].initialize()
                self._init_flags["cognitive_service"] = True
        return self._instances["cognitive_service"]

    # ID: 8f882e11-9bff-4225-9208-12660aa7c3a3
    async def get_auditor_context(self) -> AuditorContext:
        """
        Singleton factory for AuditorContext.
        Ensures we only have one view of the constitution/knowledge graph.
        """
        if "auditor_context" not in self._instances:
            async with self._lock:
                if "auditor_context" not in self._instances:
                    logger.debug("Lazy-loading AuditorContext...")
                    instance = AuditorContext(self.repo_path)
                    self._instances["auditor_context"] = instance
                    self._init_flags["auditor_context"] = False
            if not self._init_flags.get("auditor_context"):
                self._init_flags["auditor_context"] = True
        return self._instances["auditor_context"]

    # ID: 4df97396-6692-426f-a2cc-e6d29b8cefc2
    async def get_service(self, name: str) -> Any:
        """
        Lazily initializes and returns a singleton instance of a dynamic service.
        Used for services defined in the database 'runtime_services' table.
        """
        if name == "qdrant":
            return await self.get_qdrant_service()
        if name == "cognitive_service":
            return await self.get_cognitive_service()
        if name == "auditor_context":
            return await self.get_auditor_context()
        if not self._initialized:
            await self._initialize_from_db()
        if name not in self._instances:
            if name not in self._service_map:
                raise ValueError(f"Service '{name}' not found in registry.")
            class_path = self._service_map[name]
            service_class = self._import_class(class_path)
            if name in ["knowledge_service", "auditor"]:
                self._instances[name] = service_class(self.repo_path)
            else:
                self._instances[name] = service_class()
            logger.debug("Lazily initialized dynamic service: %s", name)
        return self._instances[name]


service_registry = ServiceRegistry()
