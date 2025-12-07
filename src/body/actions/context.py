# src/body/actions/context.py
"""
Defines the execution context for the PlanExecutor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from body.services.git_service import GitService
    from mind.governance.audit_context import AuditorContext
    from services.storage.file_handler import FileHandler


@dataclass
# ID: 11693175-bbaf-4a96-b97e-d3c53a6bc1f9
class PlanExecutorContext:
    """A container for services and state shared across all action handlers."""

    file_handler: FileHandler
    git_service: GitService
    auditor_context: AuditorContext
    file_content_cache: dict[str, str] = field(default_factory=dict)
