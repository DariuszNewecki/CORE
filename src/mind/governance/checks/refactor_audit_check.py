# src/mind/governance/checks/refactor_audit_check.py
"""
Enforces refactor.audit_after: run constitutional audit after any refactor.
"""

from __future__ import annotations

import time
from pathlib import Path

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity

logger = getLogger(__name__)


# ID: a1b2c3d4-e5f6-4a3b-9c8d-7e6f5a4b3c2d
class RefactorAuditCheck(BaseCheck):
    policy_rule_ids = ["refactor.audit_after"]

    # ID: d6e6c495-5c72-4ba5-a7f9-7831f003abfa
    def execute(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        # If the AuditorContext was not initialized with git_modified_files,
        # skip this check instead of crashing the whole audit.
        git_modified_files = getattr(self.context, "git_modified_files", None)
        if git_modified_files is None:
            logger.info(
                "RefactorAuditCheck: context has no 'git_modified_files'; "
                "skipping refactor audit check."
            )
            return findings

        # Any Python file in src/ modified?
        src_changes = [
            f for f in git_modified_files if f.startswith("src/") and f.endswith(".py")
        ]
        if not src_changes:
            return findings

        audit_log = Path(".core/audit.log")

        # If there is no audit log at all -> refactor without audit
        if not audit_log.exists():
            for file in src_changes:
                findings.append(
                    AuditFinding(
                        check_id="refactor.audit_after",
                        severity=AuditSeverity.ERROR,
                        message=(
                            "Code refactored without running "
                            "'core-admin check audit'."
                        ),
                        file_path=file,
                        line_number=1,
                    )
                )
            return findings

        # If audit log exists but is older than 5 minutes -> audit is stale
        if time.time() - audit_log.stat().st_mtime > 300:  # 5 minutes
            for file in src_changes:
                findings.append(
                    AuditFinding(
                        check_id="refactor.audit_after",
                        severity=AuditSeverity.ERROR,
                        message=(
                            "Refactor detected, but audit is stale (>5 min). "
                            "Run 'core-admin check audit'."
                        ),
                        file_path=file,
                        line_number=1,
                    )
                )

        return findings
