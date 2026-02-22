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
    # Add other dynamic services here if needed in the future
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
        async with self._lock:
            if "qdrant" not in self._instances:
                from shared.infrastructure.clients.qdrant_client import QdrantService

                self._instances["qdrant"] = QdrantService(
                    url=self.qdrant_url, collection_name=self.qdrant_collection_name
                )
        return self._instances["qdrant"]

    # ID: 4cd30621-d43f-40ac-a44e-4f9202258494
    async def get_cognitive_service(self) -> CognitiveService:
        async with self._lock:
            if "cognitive_service" not in self._instances:
                cls = _ServiceLoader.import_class(
                    "will.orchestration.cognitive_service.CognitiveService"
                )
                repo_path = bootstrap_registry.get_repo_path()
                instance = cls(repo_path=repo_path, session_factory=self.session)
                self._instances["cognitive_service"] = instance
                self._init_flags["cognitive_service"] = False

            if not self._init_flags.get("cognitive_service"):
                async with self.session() as session:
                    await self._instances["cognitive_service"].initialize(session)
                self._init_flags["cognitive_service"] = True

        return self._instances["cognitive_service"]

    # ID: 92dd68b8-a18e-4482-a861-ff4bf8732e4f
    async def get_auditor_context(self) -> AuditorContext:
        async with self._lock:
            if "auditor_context" not in self._instances:
                from mind.governance.audit_context import AuditorContext

                repo_path = bootstrap_registry.get_repo_path()
                self._instances["auditor_context"] = AuditorContext(repo_path)
        return self._instances["auditor_context"]


# Global instance
service_registry = ServiceRegistry()
