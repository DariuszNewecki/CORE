# src/will/orchestration/intent_guard.py
# ID: orchestration.intent_guard

"""
DEPRECATED SHIM.

IntentGuard has moved to:
- src/mind/governance/intent_guard.py

This module remains only to avoid breaking imports while the codebase
is migrated. New code MUST import from mind.governance.intent_guard.
"""

from __future__ import annotations

from body.governance.intent_guard import (  # noqa: F401
    ConstitutionalViolationError,
    IntentGuard,
    PolicyRule,
    ViolationReport,
)
