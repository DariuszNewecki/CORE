# src/features/governance/checks/base_check.py
"""
Provides a shared base class for all constitutional audit checks to inherit from.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from features.governance.audit_context import AuditorContext


# ID: 2cb0374b-a487-4dce-bab1-c2ee8a693b0a
class BaseCheck:
    """A base class for audit checks, providing a shared context."""

    def __init__(self, context: AuditorContext):
        """
        Initializes the check with a shared auditor context.
        This common initializer serves the 'dry_by_design' principle.
        """
        self.context = context
        self.repo_root = context.repo_path
        self.intent_path = context.intent_path
        self.src_dir = context.src_dir
