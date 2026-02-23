# src/body/cli/commands/coverage/services/coverage_checker.py
"""Service for checking coverage against constitutional requirements."""

from __future__ import annotations

from typing import Any

from mind.governance.filtered_audit import run_filtered_audit
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
class CoverageChecker:
    """Checks coverage compliance against constitutional rules."""

    def __init__(self, auditor_context: Any):
        self.auditor_context = auditor_context

    # ID: c2727c81-f41c-4023-8d5b-94d90d71b1dd
    async def check_compliance(self) -> dict[str, Any]:
        """
        Check coverage against constitutional requirements.

        Returns:
            dict with keys:
                - compliant: bool
                - findings: list of violations
                - blocking_violations: list of error-level violations
        """
        findings, _executed, _stats = await run_filtered_audit(
            self.auditor_context, rule_patterns=[r"qa\.coverage\..*"]
        )

        blocking_violations = [f for f in findings if f.get("severity") == "error"]

        return {
            "compliant": len(findings) == 0,
            "findings": findings,
            "blocking_violations": blocking_violations,
        }
