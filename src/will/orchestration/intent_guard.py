# src/will/orchestration/intent_guard.py

"""
DEPRECATED SHIM.

IntentGuard has moved to:
- src/body/governance/intent_guard.py

This module remains only to avoid breaking imports while the codebase
is migrated. New code MUST import from body.governance.intent_guard.
"""

from __future__ import annotations

from body.governance.intent_guard import IntentGuard  # noqa: F401
from mind.governance.policy_rule import PolicyRule  # noqa: F401
from mind.governance.violation_report import (  # noqa: F401
    ConstitutionalViolationError,
    ViolationReport,
)
