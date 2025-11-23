# src/body/services/service_registry.py

"""
Provides a centralized, lazily-initialized service registry for CORE.
This acts as a simple dependency injection container.
"""

from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
from typing import Any

from sqlalchemy import text

from services.repositories.db.engine import get_session
from shared.config import settings
from shared.logger import getLogger

logger = getLogger(__name__)


# ID: 759b0e12-7d25-4bbb-93ad-2a9a8738f99f
class ServiceRegistry:
    """A simple singleton service locator and DI container."""

    _instances: dict[str, Any] = {}
    _service_map: dict[str, str] = {}
    _initialized = False
    _lock = asyncio.Lock()

    def __init__(self, repo_path: Path | None = None):
        self.repo_path = repo_path or settings.REPO_PATH

    async def _initialize_from_db(self):
        """Loads the service map from the database on first access."""
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
                logger.info(
                    f"ServiceRegistry initialized with {len(self._service_map)} services."
                )
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

    # ID: 7a6471d3-f8df-442f-bd72-2df8727dd47a
    async def get_service(self, name: str) -> Any:
        """Lazily initializes and returns a singleton instance of a service."""
        if not self._initialized:
            await self._initialize_from_db()
        if name not in self._instances:
            if name not in self._service_map:
                raise ValueError(f"Service '{name}' not found in registry.")
            class_path = self._service_map[name]
            service_class = self._import_class(class_path)
            if name in ["knowledge_service", "cognitive_service", "auditor"]:
                self._instances[name] = service_class(self.repo_path)
            else:
                self._instances[name] = service_class()
            logger.debug(f"Lazily initialized service: {name}")
        return self._instances[name]


service_registry = ServiceRegistry()
