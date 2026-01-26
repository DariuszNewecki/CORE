# src/body/services/service_registry.py

"""
Provides a centralized, lazily-initialized service registry for CORE.
This acts as the authoritative Dependency Injection container.

CONSTITUTIONAL FIX:
- Removed ALL imports of 'get_session' to satisfy 'logic.di.no_global_session'.
- Implements Late-Binding Factory pattern for database access.

NO-LEGACY MODE (2026-01):
- CognitiveService is wired via the constitutional pattern only.
- ServiceRegistry must NOT inject Qdrant into CognitiveService.
- ServiceRegistry owns session lifecycle; Will never opens sessions.
"""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy import text

from mind.governance.audit_context import AuditorContext
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.infrastructure.clients.qdrant_client import QdrantService
    from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)


# ID: fde25013-c11d-4c42-86e2-243ddd3ae10b
class ServiceRegistry:
    """
    A singleton service locator and DI container.
    """

    _instances: ClassVar[dict[str, Any]] = {}
    _service_map: ClassVar[dict[str, str]] = {}
    _initialized: ClassVar[bool] = False
    _init_flags: ClassVar[dict[str, bool]] = {}
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    # CONSTITUTIONAL FIX: Placeholder for the session factory.
    # Handled via prime() to avoid hard-coded imports.
    _session_factory: ClassVar[Callable[[], Any] | None] = None

    def __init__(
        self,
        repo_path: Path | None = None,
        qdrant_url: str | None = None,
        qdrant_collection_name: str | None = None,
    ):
        self.repo_path = repo_path
        self.qdrant_url = qdrant_url
        self.qdrant_collection_name = qdrant_collection_name

    # ID: e089ea52-de6a-4c32-9235-9800da8d24c3
    def configure(
        self,
        *,
        repo_path: Path | None = None,
        qdrant_url: str | None = None,
        qdrant_collection_name: str | None = None,
    ) -> None:
        if repo_path is not None:
            self.repo_path = repo_path
        if qdrant_url is not None:
            self.qdrant_url = qdrant_url
        if qdrant_collection_name is not None:
            self.qdrant_collection_name = qdrant_collection_name

    @classmethod
    # ID: 1efcada0-bc76-4cc0-8e8c-379e47d04101
    def session(cls):
        """
        Returns an async session context manager using the primed factory.

        Usage:
            async with service_registry.session() as session:
                ...
        """
        if not cls._session_factory:
            raise RuntimeError(
                "ServiceRegistry error: session() called before prime(). "
                "The application entry point must call service_registry.prime(session_factory)."
            )
        return cls._session_factory()

    @classmethod
    # ID: ae9d47fa-c850-4800-ba2d-5992aa744bce
    def prime(cls, session_factory: Callable) -> None:
        """
        Primes the registry with infrastructure factories.
        MUST be called by the application entry point (Sanctuary).
        """
        cls._session_factory = session_factory
        logger.debug("ServiceRegistry primed with session factory.")

    async def _initialize_from_db(self) -> None:
        """Loads the dynamic service map from the database on first access."""
        async with self._lock:
            if self._initialized:
                return

            if not self._session_factory:
                logger.warning("ServiceRegistry accessed before being primed.")
                return

            logger.info("Initializing ServiceRegistry from database...")

            try:
                async with self._session_factory() as session:
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

    def _ensure_qdrant_instance(self) -> None:
        """Internal helper to create Qdrant instance if missing."""
        if "qdrant" in self._instances:
            return

        logger.debug("Lazy-loading QdrantService...")
        from shared.infrastructure.clients.qdrant_client import QdrantService

        if not self.qdrant_url or not self.qdrant_collection_name:
            raise RuntimeError(
                "ServiceRegistry is missing qdrant configuration. "
                "Call configure() before requesting qdrant service."
            )

        instance = QdrantService(
            url=self.qdrant_url, collection_name=self.qdrant_collection_name
        )
        self._instances["qdrant"] = instance
        self._init_flags["qdrant"] = False

    # ID: 8e8fc0c0-11df-4bd8-b365-15c255075d04
    async def get_qdrant_service(self) -> QdrantService:
        """Authoritative, lazy, singleton access to Qdrant."""
        if "qdrant" not in self._instances:
            async with self._lock:
                self._ensure_qdrant_instance()
            self._init_flags["qdrant"] = True
        return self._instances["qdrant"]

    # ID: e87e3db8-9a2f-4bed-b41e-3ebea0f3b8ef
    async def get_cognitive_service(self) -> CognitiveService:
        """
        Authoritative, lazy, singleton access to CognitiveService.

        NO-LEGACY MODE:
        - CognitiveService is constructed without Qdrant injection.
        - ServiceRegistry owns DB session lifecycle and initializes the service.
        """
        if "cognitive_service" not in self._instances:
            async with self._lock:
                if "cognitive_service" not in self._instances:
                    logger.debug("Lazy-loading CognitiveService...")
                    from will.orchestration.cognitive_service import CognitiveService

                    if not self.repo_path:
                        raise RuntimeError(
                            "ServiceRegistry is missing repo_path. "
                            "Call configure() before requesting cognitive service."
                        )

                    instance = CognitiveService(repo_path=self.repo_path)
                    self._instances["cognitive_service"] = instance
                    self._init_flags["cognitive_service"] = False

            if not self._init_flags.get("cognitive_service"):
                if not self._session_factory:
                    raise RuntimeError(
                        "ServiceRegistry error: cognitive_service requested before prime(). "
                        "The application entry point must call service_registry.prime(session_factory)."
                    )

                logger.debug("Initializing CognitiveService (Mind load + config)...")
                async with self.session() as session:  # type: ignore[assignment]
                    # CognitiveService MUST be initialized with a session in this architecture.
                    await self._instances["cognitive_service"].initialize(session)  # type: ignore[arg-type]

                self._init_flags["cognitive_service"] = True

        return self._instances["cognitive_service"]

    # ID: 8f882e11-9bff-4225-9208-12660aa7c3a3
    async def get_auditor_context(self) -> AuditorContext:
        """Singleton factory for AuditorContext."""
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
        """Lazily initializes and returns a singleton instance of a dynamic service."""
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
