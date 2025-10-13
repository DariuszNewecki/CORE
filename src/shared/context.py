# src/shared/context.py
"""
Defines the CoreContext, a dataclass that holds singleton instances of all major
services, enabling explicit dependency injection throughout the application.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
# ID: 9f1dd7c7-1cb2-435d-bd07-b7d436c9459f
class CoreContext:
    """
    A container for shared services, passed explicitly to commands.

    NOTE: Fields are typed as 'Any' to avoid cross-domain imports from here.
    Concrete types are created/wired in the CLI layer.
    """

    git_service: Any
    cognitive_service: Any
    knowledge_service: Any
    qdrant_service: Any
    auditor_context: Any
    file_handler: Any
    planner_config: Any
    _is_test_mode: bool = False  # <-- ADD THIS LINE
