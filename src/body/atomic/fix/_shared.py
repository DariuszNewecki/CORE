# src/body/atomic/fix/_shared.py

"""
Shared helpers for the fix.* atomic actions.

Split from the former body/atomic/fix_actions.py (one action per module,
#806); this module carries only cross-action helpers, never actions.
"""

from __future__ import annotations

from typing import Any

from mind.governance.violation_report import ConstitutionalViolationError


def _error_data(exc: Exception, **extra: Any) -> dict[str, Any]:
    """Build ActionResult.data for an exception, preserving structure when available.

    ConstitutionalViolationError carries the full list[ViolationReport] that
    IntentGuard produced; we serialize it via to_dict() so rule_name, path,
    and source_policy survive the persistence hop into proposal.execution_results.
    Any other exception type degrades cleanly to the legacy flat {"error": str(e)}
    shape, so this helper is safe to adopt per-action without coordinated changes
    elsewhere.
    """
    if isinstance(exc, ConstitutionalViolationError):
        return {**exc.to_dict(), **extra}
    return {"error": str(exc), **extra}
