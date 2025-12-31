# src/body/atomic/__init__.py
# ID: atomic.init
"""
Atomic Actions - Constitutional Action System
"""

from __future__ import annotations

# Import modules to trigger registration
from body.atomic import file_ops, fix_actions, sync_actions
from body.atomic.file_ops import (
    action_create_file,
    action_edit_file,
    action_read_file,
)
from body.atomic.fix_actions import (
    action_fix_docstrings,
    action_fix_headers,
    action_fix_ids,
    action_fix_logging,
)

# Re-export action functions
from body.atomic.fix_actions import (
    action_format_code as action_fix_format,
)
from body.atomic.registry import action_registry, register_action
from body.atomic.sync_actions import (
    action_sync_code_vectors,
    action_sync_constitutional_vectors,
    action_sync_database,
)


__all__ = [
    "action_create_file",
    "action_edit_file",
    "action_fix_docstrings",
    "action_fix_format",
    "action_fix_headers",
    "action_fix_ids",
    "action_fix_logging",
    "action_read_file",
    "action_registry",
    "action_sync_code_vectors",
    "action_sync_constitutional_vectors",
    "action_sync_database",
    "register_action",
]
