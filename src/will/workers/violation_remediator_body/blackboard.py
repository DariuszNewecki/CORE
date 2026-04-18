# src/will/workers/violation_remediator_body/blackboard.py
"""
Blackboard interaction helpers for ViolationRemediator.

Responsibility: claim, release, mark, and post findings on the Blackboard.
No LLM calls. No file writes.
"""

from __future__ import annotations

import json
from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)

_SOURCE_SUBJECT = "audit.violation"
_FAILED_SUBJECT = "audit.remediation.failed"
_CLAIM_LIMIT = 50


# ID: 35d0a1e2-de06-43d5-8bab-852f34171cb3
class BlackboardMixin:
    """
    Mixin providing all Blackboard interaction methods for ViolationRemediator.

    Requires self._ctx and self._target_rule to be set by the host class.
    Requires self._write to be set by the host class.
    Requires self.post_finding() from Worker base.
    """

    async def _claim_open_findings(self) -> list[dict[str, Any]]:
        """
        Atomically claim open audit.violation findings for the target rule,
        ordered by severity (critical first) then by creation time.

        Uses FOR UPDATE SKIP LOCKED to prevent double-claiming across
        concurrent worker instances.
        """
        bb = await self._ctx.registry.get_blackboard_service()
        return await bb.claim_violation_findings(
            prefix=f"{_SOURCE_SUBJECT}::%",
            limit=_CLAIM_LIMIT,
            claimed_by=self._worker_uuid,
        )

    async def _mark_findings(self, findings: list[dict[str, Any]], status: str) -> None:
        """Batch-update status of a list of findings."""
        for finding in findings:
            await self._mark_finding(finding["id"], status)

    async def _mark_finding(self, finding_id: str, status: str) -> None:
        """Update the status of a single blackboard finding by ID."""
        bb = await self._ctx.registry.get_blackboard_service()
        await bb.update_entry_status(finding_id, status)

    async def _post_failed(
        self,
        file_path: str,
        findings: list[dict[str, Any]],
        reason: str,
    ) -> None:
        """Post a failure finding to the blackboard."""
        await self.post_finding(
            subject=f"{_FAILED_SUBJECT}::{file_path}",
            payload={
                "file_path": file_path,
                "rule": self._target_rule,
                "reason": reason,
                "write": self._write,
                "finding_ids": [finding["id"] for finding in findings],
            },
        )

    def _build_violations_summary(self, findings: list[dict[str, Any]]) -> str:
        """Produce a JSON summary of violations for the LLM prompt."""
        violations = []
        for finding in findings:
            payload = finding.get("payload") or {}
            violations.append(
                {
                    "rule": payload.get("rule", self._target_rule),
                    "file_path": payload.get("file_path"),
                    "line_number": payload.get("line_number"),
                    "message": payload.get("message", ""),
                    "severity": payload.get("severity", "warning"),
                }
            )
        return json.dumps(violations, indent=2)

    def _check_atomic_action_coverage(
        self, findings: list[dict[str, Any]]
    ) -> str | None:
        """Check if all finding rules map to an ACTIVE atomic action.

        Returns the action_id if every rule in *findings* maps to the same
        ACTIVE action with confidence >= 0.80. Returns None otherwise
        (mixed actions, unmapped rules, or low confidence).
        """
        from body.autonomy.audit_analyzer import _load_remediation_map
        from shared.path_resolver import PathResolver

        try:
            path_resolver = PathResolver(self._ctx.git_service.repo_path)
            remediation_map = _load_remediation_map(path_resolver)
        except Exception:
            return None

        if not remediation_map:
            return None

        mapped_actions: set[str] = set()
        for finding in findings:
            payload = finding.get("payload") or {}
            rule = payload.get("rule") or payload.get("check_id") or ""
            entry = remediation_map.get(rule)
            if (
                entry
                and entry.get("status") == "ACTIVE"
                and (entry.get("confidence") or 0) >= 0.80
            ):
                mapped_actions.add(entry["action"])
            else:
                return None

        # Only defer if all findings map to a single atomic action.
        if len(mapped_actions) == 1:
            return mapped_actions.pop()
        return None
