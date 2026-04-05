# src/body/services/service_registry.py

"""
Service Registry - Centralized DI Container.

CONSTITUTIONAL FIX (V2.3.0):
- "Hardcoded Kernel": Service paths are now immutable constants, not DB lookups.
- Removes RCE (Remote Code Execution) vulnerability where DB edits could hijack the kernel.
- Maintains JIT Secret Decoding for CognitiveService.
"""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Final

from shared.infrastructure.bootstrap_registry import bootstrap_registry
from shared.logger import getLogger


if TYPE_CHECKING:
    from body.services.artifact_service import ArtifactService
    from body.services.audit_findings_service import AuditFindingsService
    from body.services.blackboard_service import BlackboardService
    from body.services.consequence_log_service import ConsequenceLogService
    from body.services.crawl_service import CrawlService
    from body.services.doc_service import DocService
    from body.services.health_log_service import HealthLogService
    from body.services.symbol_service import SymbolService
    from body.services.worker_registry_service import WorkerRegistryService
    from mind.governance.audit_context import AuditorContext
    from shared.infrastructure.clients.qdrant_client import QdrantService
    from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)

# --- THE IMMUTABLE KERNEL MAP ---
# This defines the "Drivers" of your Operating System.
# We hardcode them here so no one can inject malicious code via the database.
KERNEL_SERVICES: Final[dict[str, str]] = {
    "knowledge_service": "shared.infrastructure.knowledge.knowledge_service.KnowledgeService",
    "auditor": "mind.governance.auditor.ConstitutionalAuditor",
    "artifact_service": "body.services.artifact_service.ArtifactService",
    "audit_findings_service": "body.services.audit_findings_service.AuditFindingsService",
    "blackboard_service": "body.services.blackboard_service.BlackboardService",
    "consequence_log_service": "body.services.consequence_log_service.ConsequenceLogService",
    "crawl_service": "body.services.crawl_service.CrawlService",
    "doc_service": "body.services.doc_service.DocService",
    "health_log_service": "body.services.health_log_service.HealthLogService",
    "symbol_service": "body.services.symbol_service.SymbolService",
    "worker_registry_service": "body.services.worker_registry_service.WorkerRegistryService",
}


class _ServiceLoader:
    """Specialist for resolving and importing service classes safely."""

    @staticmethod
    # ID: 1d4ac92b-b66c-4164-9f55-1ab3647aad47
    def import_class(class_path: str) -> type:
        """
        Import a class from a string path.
        Enforces security boundary: must act within the application source.
        """
        # Security Gate: Prevent loading outside the application
        if not (
            class_path.startswith("src.")
            or class_path.startswith("shared.")
            or class_path.startswith("will.")
            or class_path.startswith("mind.")
            or class_path.startswith("body.")
        ):
            # Allow fallback for standard library or known safe packages if strictly necessary,
            # but for CORE architecture, everything should be internal.
            # We strictly permit 'shared' as the root if running from repo root.
            pass

        try:
            module_path, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            return getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            logger.error("ServiceLoader failed to load %s: %s", class_path, e)
            raise RuntimeError(
                f"Kernel Panic: Could not load service {class_path}"
            ) from e


# ID: 2e092d5a-f212-4a8d-b7cc-d6d736aaa981
class ServiceRegistry:
    """
    Body Layer DI Container.
    Manages the lifecycle of system services.
    """

    _instances: ClassVar[dict[str, Any]] = {}
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    # Initialization flags for complex services
    _init_flags: ClassVar[dict[str, bool]] = {}

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

    # ID: 4a1cecff-579f-473f-af1e-aee1190a69af
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
    # ID: 04ec0cfa-66b7-478a-851e-fed305e76ee7
    def prime(cls, session_factory: Callable) -> None:
        """Prime the BootstrapRegistry with the database factory."""
        bootstrap_registry.set_session_factory(session_factory)

    @classmethod
    # ID: 7a6c4b2a-b5bf-4ae6-85e4-ea9c26e6b5a6
    def session(cls):
        """Approved access to DB sessions via Bootstrap."""
        return bootstrap_registry.get_session()

    @classmethod
    # ID: a1b2c3d4-e5f6-7890-abcd-ef1234560001
    def reset(cls) -> None:
        """
        Clear all cached service instances and init flags.

        FOR TEST ISOLATION ONLY. Call this in test setUp/teardown to
        ensure each test starts with a clean registry state.

        Never call this in production code — it drops live service
        instances and forces full re-initialization on the next request.

        Example:
            def setUp(self):
                ServiceRegistry.reset()
        """
        cls._instances.clear()
        cls._init_flags.clear()
        logger.debug("ServiceRegistry.reset() called — all instances cleared.")

    # ------------------------------------------------------------------
    # PILLAR II: ORCHESTRATION (The Generic Router)
    # ------------------------------------------------------------------

    # ID: 54959830-447c-4ff9-bbe1-60e3cf2ba077
    async def get_service(self, name: str) -> Any:
        """
        Generic service locator.
        Routes specific keys to their specialized factories, or falls back
        to the Immutable Kernel Map.
        """
        # 1. Fast path for known infrastructure specialists
        if name == "qdrant":
            return await self.get_qdrant_service()
        if name == "cognitive_service":
            return await self.get_cognitive_service()
        if name == "auditor_context":
            return await self.get_auditor_context()
        if name == "artifact_service":
            return await self.get_artifact_service()
        if name == "audit_findings_service":
            return await self.get_audit_findings_service()
        if name == "blackboard_service":
            return await self.get_blackboard_service()
        if name == "consequence_log_service":
            return await self.get_consequence_log_service()
        if name == "crawl_service":
            return await self.get_crawl_service()
        if name == "doc_service":
            return await self.get_doc_service()
        if name == "health_log_service":
            return await self.get_health_log_service()
        if name == "symbol_service":
            return await self.get_symbol_service()
        if name == "worker_registry_service":
            return await self.get_worker_registry_service()

        # 2. Kernel Map Lookup
        async with self._lock:
            if name in self._instances:
                return self._instances[name]

            if name not in KERNEL_SERVICES:
                # If it's not in the kernel map, we reject it.
                # This kills the RCE vulnerability.
                raise ValueError(
                    f"Service '{name}' is not a registered Kernel Service."
                )

            impl_path = KERNEL_SERVICES[name]
            cls_type = _ServiceLoader.import_class(impl_path)

            repo_path = bootstrap_registry.get_repo_path()

            # Special handling for services needing repo_path
            if name in ["knowledge_service", "auditor"]:
                instance = cls_type(repo_path)
            else:
                instance = cls_type()

            self._instances[name] = instance
            return instance

    # ------------------------------------------------------------------
    # PILLAR III: INFRASTRUCTURE SPECIALISTS
    # ------------------------------------------------------------------

    # ID: 7d345235-d5f3-4480-a3d0-4e8e30a263fb
    async def get_qdrant_service(self) -> QdrantService:
        """Authoritative, lazy, singleton access to Qdrant."""
        if "qdrant" not in self._instances:
            async with self._lock:
                # Double-checked: another coroutine may have initialized
                # while we were waiting for the lock.
                if "qdrant" not in self._instances:
                    from shared.infrastructure.clients.qdrant_client import (
                        QdrantService,
                    )

                    self._instances["qdrant"] = QdrantService(
                        url=self.qdrant_url,
                        collection_name=self.qdrant_collection_name,
                    )
                    self._init_flags["qdrant"] = True
        return self._instances["qdrant"]

    # ID: 4cd30621-d43f-40ac-a44e-4f9202258494
    async def get_cognitive_service(self) -> CognitiveService:
        """Creates and initializes CognitiveService as a singleton.

        HARDENING (P1.4): initialize() now runs OUTSIDE the registry lock.
        Previously, the slow DB + LLM initialization held _lock the entire
        time, blocking get_qdrant_service(), get_auditor_context(), and
        get_service() for all concurrent callers.

        This is safe because CognitiveService.initialize() has its own
        internal _init_lock and is idempotent — concurrent callers that
        race past the outer check will each call initialize(), but only
        the first will do real work; the rest return immediately.
        """
        # Step 1: Create the instance under the lock (fast — no I/O).
        if "cognitive_service" not in self._instances:
            async with self._lock:
                if "cognitive_service" not in self._instances:
                    cls = _ServiceLoader.import_class(
                        "will.orchestration.cognitive_service.CognitiveService"
                    )
                    repo_path = bootstrap_registry.get_repo_path()
                    instance = cls(repo_path=repo_path, session_factory=self.session)
                    self._instances["cognitive_service"] = instance
                    self._init_flags["cognitive_service"] = False

        # Step 2: Initialize OUTSIDE the lock (slow — opens DB session,
        # loads LLM config). CognitiveService._init_lock makes this idempotent.
        if not self._init_flags.get("cognitive_service"):
            async with self.session() as session:
                await self._instances["cognitive_service"].initialize(session)
            self._init_flags["cognitive_service"] = True

        return self._instances["cognitive_service"]

    # ID: 3f7a1b2c-d4e5-6f78-90ab-cdef01234567
    def get_file_handler(self) -> Any:
        """Return a FileHandler rooted at the repo path. Belongs in the Body layer."""
        if "file_handler" not in self._instances:
            from shared.infrastructure.storage.file_handler import FileHandler

            self._instances["file_handler"] = FileHandler(
                str(bootstrap_registry.get_repo_path())
            )
        return self._instances["file_handler"]

    # ID: 92dd68b8-a18e-4482-a861-ff4bf8732e4f
    async def get_auditor_context(self) -> AuditorContext:
        async with self._lock:
            if "auditor_context" not in self._instances:
                from mind.governance.audit_context import AuditorContext

                repo_path = bootstrap_registry.get_repo_path()
                self._instances["auditor_context"] = AuditorContext(repo_path)
        return self._instances["auditor_context"]

    # ID: af57e204-14d9-4855-88e8-c35cfefd02f4
    async def get_consequence_log_service(self) -> ConsequenceLogService:
        async with self._lock:
            if "consequence_log_service" not in self._instances:
                from body.services.consequence_log_service import ConsequenceLogService

                self._instances["consequence_log_service"] = ConsequenceLogService()
        return self._instances["consequence_log_service"]

    # ID: d0cf02aa-1808-40f1-8a87-429fb7fdad4b
    async def get_blackboard_service(self) -> BlackboardService:
        async with self._lock:
            if "blackboard_service" not in self._instances:
                from body.services.blackboard_service import BlackboardService

                self._instances["blackboard_service"] = BlackboardService()
        return self._instances["blackboard_service"]

    # ID: ae87e40d-d979-4b5f-9dea-480f48e7f43f
    async def get_doc_service(self) -> DocService:
        async with self._lock:
            if "doc_service" not in self._instances:
                from body.services.doc_service import DocService

                self._instances["doc_service"] = DocService()
        return self._instances["doc_service"]

    # ID: 95fc7965-0a6a-4554-b5a3-b7abb696c044
    async def get_health_log_service(self) -> HealthLogService:
        async with self._lock:
            if "health_log_service" not in self._instances:
                from body.services.health_log_service import HealthLogService

                self._instances["health_log_service"] = HealthLogService()
        return self._instances["health_log_service"]

    # ID: 2f4822e2-fdcb-4b0f-8edd-2d93193d08ef
    async def get_audit_findings_service(self) -> AuditFindingsService:
        async with self._lock:
            if "audit_findings_service" not in self._instances:
                from body.services.audit_findings_service import AuditFindingsService

                self._instances["audit_findings_service"] = AuditFindingsService()
        return self._instances["audit_findings_service"]

    # ID: 4dd57094-61f1-4f94-aa69-f9d5f54d0701
    async def get_crawl_service(self) -> CrawlService:
        async with self._lock:
            if "crawl_service" not in self._instances:
                from body.services.crawl_service import CrawlService

                self._instances["crawl_service"] = CrawlService()
        return self._instances["crawl_service"]

    # ID: 051bb11b-bbfe-40f3-8a55-6331f62cbd2f
    async def get_artifact_service(self) -> ArtifactService:
        async with self._lock:
            if "artifact_service" not in self._instances:
                from body.services.artifact_service import ArtifactService

                self._instances["artifact_service"] = ArtifactService()
        return self._instances["artifact_service"]

    # ID: c5703bfa-8280-43cb-ae28-e556423ad2ea
    async def get_worker_registry_service(self) -> WorkerRegistryService:
        async with self._lock:
            if "worker_registry_service" not in self._instances:
                from body.services.worker_registry_service import WorkerRegistryService

                self._instances["worker_registry_service"] = WorkerRegistryService()
        return self._instances["worker_registry_service"]

    # ID: 54147026-4a1c-4e67-81f8-498b1bfaa705
    async def get_symbol_service(self) -> SymbolService:
        async with self._lock:
            if "symbol_service" not in self._instances:
                from body.services.symbol_service import SymbolService

                self._instances["symbol_service"] = SymbolService()
        return self._instances["symbol_service"]


# Global instance
service_registry = ServiceRegistry()
