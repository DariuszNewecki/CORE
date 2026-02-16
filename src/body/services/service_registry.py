# src/body/services/service_registry.py

"""
Service Registry - Centralized DI Container.

CONSTITUTIONAL FIX (V2.3.0):
- JIT Secret Decoding: Now injects the session factory into CognitiveService.
- This prevents "Detached Session" errors when accessing encrypted secrets
  (API keys) during long-running tasks like vectorization.
"""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy import text

from shared.infrastructure.bootstrap_registry import bootstrap_registry
from shared.logger import getLogger


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext
    from shared.infrastructure.clients.qdrant_client import QdrantService
    from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)


# ID: c3f0d5e1-890a-42bc-9d7b-1234567890ab
class _ServiceLoader:
    """Specialist for resolving and importing service classes."""

    @staticmethod
    # ID: db5b83fc-ede6-4b7b-b03c-f6d4c61baa0d
    def import_class(class_path: str) -> type:
        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)

    @staticmethod
    # ID: c24ae362-604e-4fce-aa4b-7e90f85c1e4f
    async def fetch_map_from_db() -> dict[str, str]:
        """Loads the dynamic service map using the bootstrap session."""
        service_map = {}
        try:
            async with bootstrap_registry.get_session() as session:
                result = await session.execute(
                    text("SELECT name, implementation FROM core.runtime_services")
                )
                for row in result:
                    service_map[row.name] = row.implementation
            return service_map
        except Exception as e:
            logger.error("ServiceRegistry: Failed to load map from DB: %s", e)
            return {}


# ID: fde25013-c11d-4c42-86e2-243ddd3ae10b
class ServiceRegistry:
    """
    Body Layer DI Container.
    """

    _instances: ClassVar[dict[str, Any]] = {}
    _service_map: ClassVar[dict[str, str]] = {}
    _initialized: ClassVar[bool] = False
    _init_flags: ClassVar[dict[str, bool]] = {}
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    def __init__(
        self,
        repo_path: Path | None = None,
        qdrant_url: str | None = None,
        qdrant_collection_name: str | None = None,
    ):
        self.repo_path = repo_path
        self.qdrant_url = qdrant_url
        self.qdrant_collection_name = qdrant_collection_name

    # ------------------------------------------------------------------
    # PILLAR I: CONFIGURATION & SESSION MGMT
    # ------------------------------------------------------------------

    # ID: 4463d328-1da1-458f-9407-102a943f194d
    def configure(self, **kwargs: Any) -> None:
        """Update infrastructure coordinates and sync with Bootstrap."""
        if "repo_path" in kwargs:
            self.repo_path = kwargs["repo_path"]
            bootstrap_registry.set_repo_path(self.repo_path)
        if "qdrant_url" in kwargs:
            self.qdrant_url = kwargs["qdrant_url"]
        if "qdrant_collection_name" in kwargs:
            self.qdrant_collection_name = kwargs["qdrant_collection_name"]

    @classmethod
    # ID: 73d9101b-c330-44bf-8bb0-a7eb3415bbdb
    def prime(cls, session_factory: Callable) -> None:
        """Prime the BootstrapRegistry with the database factory."""
        bootstrap_registry.set_session_factory(session_factory)

    @classmethod
    # ID: 37811f6d-e495-4035-ba40-21a9f99e1e69
    def session(cls):
        """Approved access to DB sessions via Bootstrap."""
        return bootstrap_registry.get_session()

    # ------------------------------------------------------------------
    # PILLAR II: ORCHESTRATION
    # ------------------------------------------------------------------

    # ID: 249e23e5-ed2a-4140-a3ca-985cd147996b
    async def get_service(self, name: str) -> Any:
        if name == "qdrant":
            return await self.get_qdrant_service()
        if name == "cognitive_service":
            return await self.get_cognitive_service()
        if name == "auditor_context":
            return await self.get_auditor_context()

        async with self._lock:
            if not self._initialized:
                self._service_map = await _ServiceLoader.fetch_map_from_db()
                self._initialized = True

        if name not in self._instances:
            if name not in self._service_map:
                raise ValueError(f"Service '{name}' not found.")

            impl_path = self._service_map[name]
            cls_type = _ServiceLoader.import_class(impl_path)

            repo_path = bootstrap_registry.get_repo_path()

            if name in ["knowledge_service", "auditor"]:
                self._instances[name] = cls_type(repo_path)
            else:
                self._instances[name] = cls_type()

        return self._instances[name]

    # ------------------------------------------------------------------
    # PILLAR III: INFRASTRUCTURE SPECIALISTS
    # ------------------------------------------------------------------

    # ID: a23b5769-c7b5-413d-92f4-cec92dceff74
    async def get_qdrant_service(self) -> QdrantService:
        async with self._lock:
            if "qdrant" not in self._instances:
                from shared.infrastructure.clients.qdrant_client import QdrantService

                self._instances["qdrant"] = QdrantService(
                    url=self.qdrant_url, collection_name=self.qdrant_collection_name
                )
        return self._instances["qdrant"]

    # ID: f79fd19b-069b-47b1-a562-e97eb4c58794
    async def get_cognitive_service(self) -> CognitiveService:
        async with self._lock:
            if "cognitive_service" not in self._instances:
                from will.orchestration.cognitive_service import CognitiveService

                repo_path = bootstrap_registry.get_repo_path()
                # CONSTITUTIONAL FIX: Inject self.session factory to handle JIT secret retrieval
                instance = CognitiveService(
                    repo_path=repo_path, session_factory=self.session
                )
                self._instances["cognitive_service"] = instance
                self._init_flags["cognitive_service"] = False

        if not self._init_flags.get("cognitive_service"):
            async with self.session() as session:
                await self._instances["cognitive_service"].initialize(session)
            self._init_flags["cognitive_service"] = True

        return self._instances["cognitive_service"]

    # ID: 0da9077a-d49c-4efc-8e8d-d0b3a8a66061
    async def get_auditor_context(self) -> AuditorContext:
        async with self._lock:
            if "auditor_context" not in self._instances:
                from mind.governance.audit_context import AuditorContext

                repo_path = bootstrap_registry.get_repo_path()
                self._instances["auditor_context"] = AuditorContext(repo_path)
        return self._instances["auditor_context"]


# Global instance
service_registry = ServiceRegistry()
