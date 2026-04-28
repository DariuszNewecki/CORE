# src/body/atomic/__init__.py
"""
Atomic Actions - Constitutional Action System
"""

from __future__ import annotations

# Import modules to trigger registration
from body.atomic import (
    build_tests_action,
    check_actions,
    crate_ops,
    file_ops,
    fix_actions,
    metadata_ops,
    modularity_fix,
    proposal_lifecycle_actions,
    sync_actions,
)
from body.atomic.build_tests_action import action_build_tests
from body.atomic.check_actions import action_check_imports
from body.atomic.crate_ops import action_create_crate
from body.atomic.file_ops import (
    action_create_file,
    action_edit_file,
    action_read_file,
)
from body.atomic.fix_actions import (
    action_fix_headers,
    action_fix_ids,
    action_fix_logging,
)

# Re-export action functions
from body.atomic.fix_actions import (
    action_format_code as action_fix_format,
)
from body.atomic.metadata_ops import action_tag_metadata
from body.atomic.modularity_fix import action_fix_modularity
from body.atomic.registry import action_registry, register_action
from body.atomic.sync_actions import (
    action_sync_code_vectors,
    action_sync_constitutional_vectors,
    action_sync_database,
)


__all__ = [
    "action_build_tests",
    "action_check_imports",
    "action_create_crate",
    "action_create_file",
    "action_edit_file",
    "action_fix_format",
    "action_fix_headers",
    "action_fix_ids",
    "action_fix_logging",
    "action_fix_modularity",
    "action_read_file",
    "action_registry",
    "action_sync_code_vectors",
    "action_sync_constitutional_vectors",
    "action_sync_database",
    "action_tag_metadata",
    "register_action",
]
