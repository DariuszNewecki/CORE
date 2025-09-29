# src/core/actions/context.py
"""
Defines the execution context for the PlanExecutor.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from core.file_handler import FileHandler
    from core.git_service import GitService
    from features.governance.audit_context import AuditorContext


# ID: 2b3c4d5e-6f7a-8b9c-0d1e2f3a4b5c
@dataclass
# ID: 11693175-bbaf-4a96-b97e-d3c53a6bc1f9
class PlanExecutorContext:
    """A container for services and state shared across all action handlers."""

    file_handler: "FileHandler"
    git_service: "GitService"
    auditor_context: "AuditorContext"
    file_content_cache: Dict[str, str] = field(default_factory=dict)
