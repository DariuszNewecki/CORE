# src/body/atomic/__init__.py
# ID: atomic.init
"""
Atomic Actions - Constitutional Action System

This module provides the atomic action architecture for dev workflows.
These actions are independent, composable, and constitutionally governed.

IMPORTANT: This is separate from body/actions/ which handles AI autonomy.
- body/actions/: ActionHandler classes for PlanExecutor (AI agents)
- body/atomic/: @atomic_action functions for CLI workflows (humans + automation)

Both systems can coexist and will eventually converge.
"""

from __future__ import annotations

# Import modules to trigger registration
from body.atomic import fix_actions, sync_actions
from body.atomic.fix_actions import (
    action_fix_docstrings,
    action_fix_headers,
    action_fix_ids,
    action_fix_logging,
)

# Re-export action functions with corrected names
from body.atomic.fix_actions import (
    action_format_code as action_fix_format,  # ← Name correction
)
from body.atomic.registry import action_registry, register_action
from body.atomic.sync_actions import (
    action_sync_code_vectors,
    action_sync_constitutional_vectors,
    action_sync_database,
)


__all__ = [
    "action_fix_docstrings",
    # Fix actions
    "action_fix_format",  # Exported as the correct name
    "action_fix_headers",
    "action_fix_ids",
    "action_fix_logging",
    # Registry
    "action_registry",
    "action_sync_code_vectors",
    "action_sync_constitutional_vectors",
    # Sync actions
    "action_sync_database",
    "register_action",
]
