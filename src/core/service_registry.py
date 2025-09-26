# src/core/service_registry.py
"""
Provides a centralized, lazily-initialized service registry for CORE.
This acts as a simple dependency injection container.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Dict

from shared.config import settings
from shared.logger import getLogger

log = getLogger("service_registry")


class ServiceRegistry:
    """A simple singleton service locator and DI container."""

    _instances: Dict[str, Any] = {}
    _service_map: Dict[str, str] = {}
    _initialized = False

    def __init__(self, repo_path: Path | None = None):
        if not self._initialized:
            # Use the repo_path from settings as the primary source of truth
            self.repo_path = repo_path or settings.REPO_PATH

            # --- THIS IS THE REFACTOR ---
            # Load the runtime_services config using the new settings object
            config = settings.load("mind.config.runtime_services")
            # --- END OF REFACTOR ---

            for service in config.get("services", []):
                self._service_map[service["name"]] = service["implementation"]

            self._initialized = True
            log.info(
                f"ServiceRegistry initialized with {len(self._service_map)} services."
            )

    def _import_class(self, class_path: str):
        """Dynamically imports a class from a string path."""
        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)

    def get_service(self, name: str) -> Any:
        """Lazily initializes and returns a singleton instance of a service."""
        if name not in self._instances:
            if name not in self._service_map:
                raise ValueError(f"Service '{name}' not found in registry.")

            class_path = self._service_map[name]
            service_class = self._import_class(class_path)

            # Simple dependency injection based on convention
            # Pass the repo_path to services that need it.
            if name in ["knowledge_service", "cognitive_service", "auditor"]:
                self._instances[name] = service_class(self.repo_path)
            else:
                self._instances[name] = service_class()

            log.debug(f"Lazily initialized service: {name}")

        return self._instances[name]


# Global instance
service_registry = ServiceRegistry()
