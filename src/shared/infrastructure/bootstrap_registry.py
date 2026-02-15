# src/shared/infrastructure/bootstrap_registry.py

"""
Bootstrap Registry - The System Ignition Point.

CONSTITUTIONAL AUTHORITY: Infrastructure (coordination)
AUTHORITY LIMITS: Cannot instantiate services or make decisions.
RESPONSIBILITIES: Hold the session factory and root path for the Body.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any


# ID: 5ee7da14-761a-4fab-b10d-9d0bead06a4c
# ID: fd1ce789-4054-4d38-83f2-55237a8e9ae9
class BootstrapRegistry:
    """
    A minimal container for system primitives.
    Allows the path and session factory to be set during different
    stages of the bootstrap process.
    """

    _session_factory: Callable[[], Any] | None = None
    _repo_path: Path | None = None

    @classmethod
    # ID: 67501a4c-d1e2-4f92-80d2-5151248c95ae
    def set_session_factory(cls, factory: Callable) -> None:
        cls._session_factory = factory

    @classmethod
    # ID: 2c9e6e00-eacf-4a4d-95a4-e72f9d390ab6
    def set_repo_path(cls, path: Path) -> None:
        cls._repo_path = Path(path).resolve()

    @classmethod
    # ID: 11917581-fad0-44cb-8833-b375d09f20e8
    def get_session(cls):
        """Standard accessor for database sessions."""
        if not cls._session_factory:
            raise RuntimeError("BootstrapRegistry: Session factory not set.")
        return cls._session_factory()

    @classmethod
    # ID: f1a0cb1d-c01c-4fd1-88b8-4f3ec7feed71
    def get_repo_path(cls) -> Path:
        if not cls._repo_path:
            # Fallback to current working directory if not explicitly set
            return Path.cwd().resolve()
        return cls._repo_path


# Global singleton
bootstrap_registry = BootstrapRegistry()
