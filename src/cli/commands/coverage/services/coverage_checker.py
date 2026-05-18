# src/cli/commands/coverage/services/coverage_checker.py
"""Service for checking coverage against constitutional requirements.

Thin client over GET /v1/coverage/check (ADR-057 D1). All data fetching
crosses the HTTP boundary via CoreApiClient — no direct calls to
mind.governance.filtered_audit (which is the API's backend, not a CLI
dependency).
"""

from __future__ import annotations

import logging
from typing import Any

from api.cli import CoreApiClient


logger = logging.getLogger(__name__)


# ID: 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
class CoverageChecker:
    """Checks coverage compliance via the API."""

    def __init__(self, auditor_context: Any = None):
        # auditor_context retained for call-site compatibility; the API
        # owns the auditor context server-side now.
        _ = auditor_context

    # ID: c2727c81-f41c-4023-8d5b-94d90d71b1dd
    async def check_compliance(self) -> dict[str, Any]:
        """Check coverage against constitutional requirements.

        Returns:
            dict with keys:
                - compliant: bool
                - findings: list of violations
                - blocking_violations: list of error-level violations
        """
        client = CoreApiClient()
        payload = await client.coverage_check()
        findings = payload.get("findings", [])
        blocking_violations = [
            f for f in findings if str(f.get("severity", "")).lower() == "error"
        ]
        return {
            "compliant": payload.get("passed", len(findings) == 0),
            "findings": findings,
            "blocking_violations": blocking_violations,
        }
