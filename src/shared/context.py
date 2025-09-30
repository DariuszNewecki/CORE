# src/shared/context.py
"""
Defines the CoreContext, a dataclass that holds singleton instances of all major
services, enabling explicit dependency injection throughout the application.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
# ID: 6ae82e74-acc2-45a1-b2a3-6cd6e596640c
class CoreContext:
    """
    A container for shared services, passed explicitly to commands.

    NOTE: Fields are typed as 'Any' to avoid cross-domain imports from here.
    Concrete types are created/wired in the CLI layer.
    """

    git_service: Any
    cognitive_service: Any
    qdrant_service: Any
    auditor_context: Any
    file_handler: Any
    planner_config: Any
