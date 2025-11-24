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

# Type checking imports only (no runtime cost)
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from services.database.session_manager import get_session
from shared.config import settings
from shared.logger import getLogger

if TYPE_CHECKING:
    from services.clients.qdrant_client import QdrantService
    from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)


# ID: 759b0e12-7d25-4bbb-93ad-2a9a8738f99f
class ServiceRegistry:
    """
    A singleton service locator and DI container.
    Manages the lifecycle of infrastructure services to ensure:
    1. Singletons (only one connection pool per service)
    2. Lazy loading (don't import heavy libs until needed)
    """

    _instances: dict[str, Any] = {}
    _service_map: dict[str, str] = {}
    _initialized = False
    _lock = asyncio.Lock()

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
                    f"Failed to initialize ServiceRegistry from DB: {e}", exc_info=True
                )
                self._initialized = False

    def _import_class(self, class_path: str):
        """Dynamically imports a class from a string path."""
        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)

    # --- Explicit Factories for Core Infrastructure ---

    # ID: 8ebb81b4-2339-4755-849c-888096781db2
    async def get_qdrant_service(self) -> QdrantService:
        """
        Authoritative, lazy, singleton access to Qdrant.
        Prevents 'split-brain' initialization where multiple clients are created.
        """
        if "qdrant" not in self._instances:
            async with self._lock:
                if "qdrant" not in self._instances:
                    logger.debug("Lazy-loading QdrantService...")
                    # Local import to prevent slow startup for non-vector commands
                    from services.clients.qdrant_client import QdrantService

                    instance = QdrantService(
                        url=settings.QDRANT_URL,
                        collection_name=settings.QDRANT_COLLECTION_NAME,
                    )
                    self._instances["qdrant"] = instance

        return self._instances["qdrant"]

    # ID: d01e52c3-5f2b-457e-babf-6df52e95bcfd
    async def get_cognitive_service(self) -> CognitiveService:
        """
        Creates CognitiveService, injecting the singleton QdrantService.
        """
        if "cognitive_service" not in self._instances:
            async with self._lock:
                if "cognitive_service" not in self._instances:
                    logger.debug("Lazy-loading CognitiveService...")
                    from will.orchestration.cognitive_service import CognitiveService

                    # DI Rule: We inject the Qdrant dependency here
                    qdrant = await self.get_qdrant_service()

                    instance = CognitiveService(
                        repo_path=self.repo_path, qdrant_service=qdrant
                    )
                    self._instances["cognitive_service"] = instance

        return self._instances["cognitive_service"]

    # --- Dynamic Service Resolution (Legacy/Plugin Support) ---

    # ID: 7a6471d3-f8df-442f-bd72-2df8727dd47a
    async def get_service(self, name: str) -> Any:
        """
        Lazily initializes and returns a singleton instance of a dynamic service.
        Used for services defined in the database 'runtime_services' table.
        """
        # Prefer explicit factories if they exist
        if name == "qdrant":
            return await self.get_qdrant_service()
        if name == "cognitive_service":
            return await self.get_cognitive_service()

        if not self._initialized:
            await self._initialize_from_db()

        if name not in self._instances:
            if name not in self._service_map:
                raise ValueError(f"Service '{name}' not found in registry.")

            class_path = self._service_map[name]
            service_class = self._import_class(class_path)

            # Basic DI based on convention
            if name in ["knowledge_service", "auditor"]:
                self._instances[name] = service_class(self.repo_path)
            else:
                self._instances[name] = service_class()

            logger.debug(f"Lazily initialized dynamic service: {name}")

        return self._instances[name]


# Global instance for simple access where DI isn't possible yet
service_registry = ServiceRegistry()
