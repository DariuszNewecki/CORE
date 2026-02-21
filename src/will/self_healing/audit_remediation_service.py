# src/will/self_healing/audit_remediation_service.py
# ID: afa7c5cd-02f7-4f73-a169-6f9aabbffa0c
"""Audit Remediation Service - The A2 Autonomy Bridge.

Orchestrates the full remediation cycle:
    Audit Findings → Pattern Matching → Fix Execution → Validation → Evidence

Constitutional alignment:
- All writes via FileHandler (IntentGuard enforcement)
- Validation mandatory (must prove improvement)
- Evidence artifacts required (full traceability)
- Mind-Body-Will separation maintained
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from body.self_healing.remediation_models import (
    RemediationMode,
    RemediationResult,
    create_remediation_result,
)
from body.services.file_service import FileService
from mind.governance.audit_context import AuditorContext
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity
from will.self_healing.remediation_evidence_writer import RemediationEvidenceWriter
from will.self_healing.remediation_executor import RemediationExecutor
from will.self_healing.remediation_pattern_matcher import RemediationPatternMatcher


logger = getLogger(__name__)


# ID: f3720fdc-1ad0-416a-b35f-c682a50b3e17
class AuditRemediationService:
    """Constitutional bridge between audit findings and autonomous remediation.

    Delegates to three focused collaborators:
    - RemediationPatternMatcher: finding → pattern resolution
    - RemediationExecutor: handler dispatch and execution
    - RemediationEvidenceWriter: validation audit and artifact persistence
    """

    def __init__(
        self,
        file_handler: FileService,
        auditor_context: AuditorContext,
        repo_root: Path,
    ) -> None:
        self.repo_root = repo_root
        self._matcher = RemediationPatternMatcher()
        self._executor = RemediationExecutor(file_handler, repo_root)
        self._evidence = RemediationEvidenceWriter(
            file_handler, auditor_context, repo_root
        )

        logger.info(
            "AuditRemediationService initialized with %d fix patterns",
            len(self._matcher.patterns),
        )

    # ID: 7b88ca76-5300-40b4-90e9-4b7b52f33f98
    async def remediate(
        self,
        findings_path: Path | None = None,
        mode: RemediationMode = RemediationMode.SAFE_ONLY,
        target_pattern: str | None = None,
        write: bool = False,
    ) -> RemediationResult:
        """Execute the complete remediation cycle.

        Args:
            findings_path: Path to audit findings JSON (defaults to reports/).
            mode: Risk tolerance for automatic fixes.
            target_pattern: If provided, only fix this pattern (e.g., "style.*").
            write: If False, dry-run mode (no actual changes).

        Returns:
            RemediationResult with complete evidence trail.
        """
        start_time = time.time()
        logger.info(
            "Starting remediation: mode=%s, write=%s, target=%s",
            mode.value,
            write,
            target_pattern or "all",
        )

        findings = await self._load_findings(findings_path)
        logger.info("Loaded %d audit findings", len(findings))

        matched, unmatched = self._matcher.match(findings, mode, target_pattern)
        logger.info(
            "Pattern matching: %d matched, %d unmatched", len(matched), len(unmatched)
        )

        fix_details = await self._executor.execute(matched, write)
        logger.info("Fix execution complete: %d attempts", len(fix_details))

        if write and any(d.status == "success" for d in fix_details):
            (
                validation_passed,
                findings_after,
                validation_path,
            ) = await self._evidence.validate_improvement(len(findings))
        else:
            validation_passed, findings_after, validation_path = (
                False,
                len(findings),
                None,
            )

        result = create_remediation_result(
            total_findings=len(findings),
            findings_by_severity=self._evidence.count_by_severity(findings),
            matched_patterns=matched,
            unmatched_findings=unmatched,
            fix_details=fix_details,
            findings_before=len(findings),
            findings_after=findings_after,
            audit_input_path=str(findings_path or self._default_findings_path()),
            remediation_output_path="",
            validation_audit_path=str(validation_path) if validation_path else None,
            duration_sec=time.time() - start_time,
        )

        evidence_path = await self._evidence.write_evidence(result)
        result.remediation_output_path = str(evidence_path)

        logger.info(
            "Remediation complete: %d/%d successful, improvement=%d, validation=%s",
            result.fixes_succeeded,
            result.fixes_attempted,
            result.improvement_delta,
            "PASSED" if result.validation_passed else "FAILED",
        )
        return result

    # ID: e8a9b0c1-d2e3-4567-efab-888888888888
    def _default_findings_path(self) -> Path:
        return self.repo_root / "reports" / "audit_findings.processed.json"

    # ID: f9b0c1d2-e3f4-5678-fabc-999999999999
    async def _load_findings(self, findings_path: Path | None) -> list[AuditFinding]:
        """Load audit findings from JSON file."""
        path = findings_path or self._default_findings_path()

        if not path.exists():
            logger.warning("Findings file not found: %s", path)
            return []

        try:
            findings_data = json.loads(path.read_text(encoding="utf-8"))
            findings = []
            for item in findings_data:
                severity_str = item.get("severity", "info")
                severity = {
                    "error": AuditSeverity.ERROR,
                    "warning": AuditSeverity.WARNING,
                }.get(severity_str, AuditSeverity.INFO)

                findings.append(
                    AuditFinding(
                        check_id=item.get("check_id", "unknown"),
                        severity=severity,
                        message=item.get("message", ""),
                        file_path=item.get("file_path"),
                        line_number=item.get("line_number"),
                        context=item.get("context", {}),
                    )
                )
            return findings

        except Exception as e:
            logger.error("Failed to load findings from %s: %s", path, e)
            return []
