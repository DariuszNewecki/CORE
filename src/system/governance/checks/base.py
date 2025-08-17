# src/system/governance/checks/base.py
"""
Provides a base class for all auditor check containers.
This helps enforce the 'dry_by_design' principle by centralizing
common initialization logic.
"""


class BaseAuditCheck:
    """Base class for a collection of auditor checks."""

    def __init__(self, context):
        """Initializes the check with a shared auditor context."""
        self.context = context