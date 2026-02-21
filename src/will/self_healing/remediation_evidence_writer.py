# src/will/self_healing/remediation_evidence_writer.py
"""Remediation Evidence Writer.

Handles validation audits and writing evidence artifacts to disk.
Single responsibility: audit validation and evidence persistence only.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from body.self_healing.remediation_models import RemediationResult
from body.services.file_service import FileService
from mind.governance.audit_context import AuditorContext
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: ff0c7381-0807-4b84-b638-5213af6ced2e
class RemediationEvidenceWriter:
    """Validates remediation results and persists evidence artifacts."""

    def __init__(
        self,
        file_handler: FileService,
        auditor_context: AuditorContext,
        repo_root: Path,
    ) -> None:
        self.file_handler = file_handler
        self.auditor = auditor_context
        self.repo_root = repo_root

    # ID: c69c8df7-5f0b-444a-a527-1b5a6376c0e6
    async def validate_improvement(
        self,
        findings_before_count: int,
    ) -> tuple[bool, int, Path | None]:
        """Re-run audit to validate that fixes reduced findings.

        Args:
            findings_before_count: Baseline finding count before fixes.

        Returns:
            Tuple of (passed, findings_after_count, audit_path).
        """
        logger.info("Running validation audit...")
        try:
            findings_after = await self.auditor.audit()
            findings_after_count = len(findings_after)
            improvement = findings_before_count - findings_after_count
            passed = improvement > 0
            audit_path = self.repo_root / "reports" / "audit_findings.json"

            logger.info(
                "Validation complete: %d → %d findings (delta=%d, passed=%s)",
                findings_before_count,
                findings_after_count,
                improvement,
                passed,
            )
            return passed, findings_after_count, audit_path

        except Exception as e:
            logger.error("Validation audit failed: %s", e)
            return False, findings_before_count, None

    # ID: 54f2ddb8-17c0-4d2a-9add-8d4f2298efcc
    async def write_evidence(self, result: RemediationResult) -> Path:
        """Write evidence artifact to reports/remediation/.

        Args:
            result: Completed remediation result to persist.

        Returns:
            Path where evidence was written.
        """
        remediation_dir = self.repo_root / "reports" / "remediation"
        remediation_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        evidence_path = remediation_dir / f"remediation_{timestamp}.json"
        latest_path = remediation_dir / "latest_remediation.json"

        evidence = {
            "session_id": result.session_id,
            "timestamp_utc": result.timestamp_utc,
            "total_findings": result.total_findings,
            "findings_by_severity": result.findings_by_severity,
            "matched_count": len(result.matched_patterns),
            "unmatched_count": len(result.unmatched_findings),
            "fixes_attempted": result.fixes_attempted,
            "fixes_succeeded": result.fixes_succeeded,
            "fixes_failed": result.fixes_failed,
            "validation_passed": result.validation_passed,
            "findings_before": result.findings_before,
            "findings_after": result.findings_after,
            "improvement_delta": result.improvement_delta,
            "duration_sec": result.duration_sec,
            "audit_input_path": result.audit_input_path,
            "validation_audit_path": result.validation_audit_path,
            "fix_details": [
                {
                    "finding_id": d.finding_id,
                    "file_path": d.file_path,
                    "action_handler": d.action_handler,
                    "status": d.status,
                    "error_message": d.error_message,
                    "duration_ms": d.duration_ms,
                }
                for d in result.fix_details
            ],
        }

        rel_path = str(evidence_path.relative_to(self.repo_root))
        self.file_handler.write_runtime_json(rel_path, evidence)

        rel_latest = str(latest_path.relative_to(self.repo_root))
        self.file_handler.write_runtime_json(rel_latest, evidence)

        logger.info("Evidence written to: %s", evidence_path)
        return evidence_path

    # ID: 9c30321f-0dd2-4175-9fc3-7341830ceddc
    def count_by_severity(self, findings) -> dict[str, int]:
        """Count findings by severity level.

        Returns:
            Dict of {"error": N, "warning": N, "info": N}.
        """
        counts = {"error": 0, "warning": 0, "info": 0}
        for finding in findings:
            severity_str = str(finding.severity)
            if severity_str in counts:
                counts[severity_str] += 1
        return counts
