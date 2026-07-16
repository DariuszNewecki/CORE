# src/body/atomic/fix/__init__.py

"""
fix.* atomic actions — one action per module.

Split from the former body/atomic/fix_actions.py (#806): 14 independently
registered, independently risk-classified actions were sharing one file
(the highest-churn file in the repo). Mirrors the sync_actions package
pattern. Importing this package registers every fix.* action — the
decorators run at module import time.

Shared helpers live in _shared.py; each action module carries exactly one
registered action, verbatim from the original file (same # ID, same
action_id, same decorators — action_risk.yaml keys and registry discovery
are unchanged).
"""

from __future__ import annotations

from body.atomic.fix.atomic_actions import action_fix_atomic_actions
from body.atomic.fix.capability_tagging import action_fix_capability_tagging
from body.atomic.fix.docstrings import action_fix_docstrings
from body.atomic.fix.duplicate_ids import action_fix_duplicate_ids
from body.atomic.fix.format_code import action_format_code
from body.atomic.fix.headers import action_fix_headers
from body.atomic.fix.ids import action_fix_ids
from body.atomic.fix.imports import action_fix_imports
from body.atomic.fix.logging_fix import action_fix_logging
from body.atomic.fix.path_resolver import action_fix_path_resolver
from body.atomic.fix.placeholders import action_fix_placeholders
from body.atomic.fix.purge_legacy_tags import action_fix_purge_legacy_tags
from body.atomic.fix.settings_access import action_fix_settings_access
from body.atomic.fix.vulture_heal import action_fix_vulture_heal


__all__ = [
    "action_fix_atomic_actions",
    "action_fix_capability_tagging",
    "action_fix_docstrings",
    "action_fix_duplicate_ids",
    "action_fix_headers",
    "action_fix_ids",
    "action_fix_imports",
    "action_fix_logging",
    "action_fix_path_resolver",
    "action_fix_placeholders",
    "action_fix_purge_legacy_tags",
    "action_fix_settings_access",
    "action_fix_vulture_heal",
    "action_format_code",
]
