# src/features/self_healing/audit_remediation_service.py
"""
Audit Remediation Service - The A2 Autonomy Bridge

This service connects constitutional governance to autonomous healing:
    Audit Findings → Pattern Matching → Deterministic Fixes → Validation → Evidence

This is the missing piece that makes CORE's constitution self-enforcing.

CONSTITUTIONAL ALIGNMENT:
- All writes via FileHandler (IntentGuard enforcement)
- Validation mandatory (must prove improvement)
- Evidence artifacts required (full traceability)
- Mind-Body-Will separation maintained
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from features.self_healing.remediation_models import (
    FixDetail,
    FixResult,
    MatchedPattern,
    RemediationMode,
    RemediationResult,
    create_remediation_result,
)
from mind.governance.audit_context import AuditorContext
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: TBD (will be assigned by dev-sync)
# ID: f3720fdc-1ad0-416a-b35f-c682a50b3e17
class AuditRemediationService:
    """
    Constitutional bridge between audit findings and autonomous remediation.

    This service:
    1. Reads audit findings from JSON
    2. Matches findings to known fix patterns
    3. Executes deterministic fixes (NO LLM in v1)
    4. Re-runs audit to validate improvement
    5. Writes evidence artifact for traceability

    Example usage:
        service = AuditRemediationService(
            file_handler=file_handler,
            auditor_context=auditor_context,
            repo_root=Path("/opt/dev/CORE"),
        )

        result = await service.remediate(
            mode=RemediationMode.SAFE_ONLY,
            write=True,
        )

        print(f"Fixed {result.fixes_succeeded} of {result.fixes_attempted} issues")
        print(f"Improvement: {result.improvement_delta} fewer violations")
    """

    def __init__(
        self,
        file_handler: FileHandler,
        auditor_context: AuditorContext,
        repo_root: Path,
    ):
        """
        Initialize the remediation service.

        Args:
            file_handler: Constitutional write gateway (ensures governance)
            auditor_context: For running validation audits
            repo_root: Repository root for path resolution
        """
        self.file_handler = file_handler
        self.auditor = auditor_context
        self.repo_root = repo_root

        # We'll define available patterns in the next step
        self.patterns = self._load_fix_patterns()

        logger.info(
            "AuditRemediationService initialized with %d fix patterns",
            len(self.patterns),
        )

    def _load_fix_patterns(self) -> list:
        """
        Load available fix patterns.

        For now, we only have ONE pattern implemented: import sorting.
        More patterns will be added as handlers are created.

        Returns:
            List of AutoFixablePattern objects
        """
        # Import here to avoid circular dependencies
        from features.autonomy.audit_analyzer import AutoFixablePattern

        # Start with just import sorting (our proof-of-concept)
        patterns = [
            AutoFixablePattern(
                check_id_pattern="style.import_order",
                action_handler="sort_imports",  # References our handler
                confidence=0.90,
                risk_level="low",
                description="Sort imports according to PEP 8",
            ),
        ]

        return patterns

    # ID: 7b88ca76-5300-40b4-90e9-4b7b52f33f98
    async def remediate(
        self,
        findings_path: Path | None = None,
        mode: RemediationMode = RemediationMode.SAFE_ONLY,
        target_pattern: str | None = None,
        write: bool = False,
    ) -> RemediationResult:
        """
        Execute the complete remediation cycle.

        Flow:
        1. Load audit findings from JSON
        2. Match findings to fix patterns
        3. Filter by mode (safe_only / medium_risk / all)
        4. Execute fixes via handlers
        5. Re-run audit to validate
        6. Write evidence artifact

        Args:
            findings_path: Path to audit findings JSON (defaults to reports/)
            mode: Risk tolerance for automatic fixes
            target_pattern: If provided, only fix this pattern (e.g., "style.*")
            write: If False, dry-run mode (no actual changes)

        Returns:
            RemediationResult with complete evidence trail
        """

        start_time = time.time()

        logger.info(
            "Starting remediation: mode=%s, write=%s, target=%s",
            mode.value,
            write,
            target_pattern or "all",
        )

        # Step 1: Load audit findings
        findings = await self._load_findings(findings_path)
        logger.info("Loaded %d audit findings", len(findings))

        # Step 2: Match findings to patterns
        matched, unmatched = await self._match_patterns(
            findings=findings,
            mode=mode,
            target_pattern=target_pattern,
        )
        logger.info(
            "Pattern matching: %d matched, %d unmatched",
            len(matched),
            len(unmatched),
        )

        # Step 3: Execute fixes
        fix_details = await self._execute_fixes(
            matched=matched,
            write=write,
        )
        logger.info("Fix execution complete: %d attempts", len(fix_details))

        # Step 4: Validate improvement (if we actually wrote changes)
        if write and any(d.status == "success" for d in fix_details):
            (
                validation_passed,
                findings_after,
                validation_path,
            ) = await self._validate_improvement(len(findings))
        else:
            # Dry-run or no successful fixes - skip validation
            validation_passed = False
            findings_after = len(findings)
            validation_path = None

        # Step 5: Build result object
        findings_by_severity = self._count_by_severity(findings)

        duration_sec = time.time() - start_time

        result = create_remediation_result(
            total_findings=len(findings),
            findings_by_severity=findings_by_severity,
            matched_patterns=matched,
            unmatched_findings=unmatched,
            fix_details=fix_details,
            findings_before=len(findings),
            findings_after=findings_after,
            audit_input_path=str(findings_path or self._default_findings_path()),
            remediation_output_path="",  # Will be set by _write_evidence
            validation_audit_path=str(validation_path) if validation_path else None,
            duration_sec=duration_sec,
        )

        # Step 6: Write evidence artifact
        evidence_path = await self._write_evidence(result)
        result.remediation_output_path = str(evidence_path)

        logger.info(
            "Remediation complete: %d/%d successful, improvement=%d, validation=%s",
            result.fixes_succeeded,
            result.fixes_attempted,
            result.improvement_delta,
            "PASSED" if result.validation_passed else "FAILED",
        )

        return result

    def _default_findings_path(self) -> Path:
        """Get default path to audit findings."""
        return self.repo_root / "reports" / "audit_findings.processed.json"

    async def _load_findings(
        self,
        findings_path: Path | None,
    ) -> list[AuditFinding]:
        """
        Load audit findings from JSON file.

        Args:
            findings_path: Path to findings file (or None for default)

        Returns:
            List of AuditFinding objects
        """

        path = findings_path or self._default_findings_path()

        if not path.exists():
            logger.warning("Findings file not found: %s", path)
            return []

        try:
            # Read JSON
            content = path.read_text(encoding="utf-8")
            findings_data = json.loads(content)

            # Convert to AuditFinding objects
            findings = []
            for item in findings_data:
                # Map severity string to enum
                severity_str = item.get("severity", "info")
                if severity_str == "error":
                    severity = AuditSeverity.ERROR
                elif severity_str == "warning":
                    severity = AuditSeverity.WARNING
                else:
                    severity = AuditSeverity.INFO

                finding = AuditFinding(
                    check_id=item.get("check_id", "unknown"),
                    severity=severity,
                    message=item.get("message", ""),
                    file_path=item.get("file_path"),
                    line_number=item.get("line_number"),
                    context=item.get("context", {}),
                )
                findings.append(finding)

            return findings

        except Exception as e:
            logger.error("Failed to load findings from %s: %s", path, e)
            return []

    async def _match_patterns(
        self,
        findings: list[AuditFinding],
        mode: RemediationMode,
        target_pattern: str | None,
    ) -> tuple[list[MatchedPattern], list[AuditFinding]]:
        """
        Match findings to fix patterns.

        Args:
            findings: List of audit findings
            mode: Remediation mode (controls risk tolerance)
            target_pattern: Optional filter (only match this pattern)

        Returns:
            Tuple of (matched_patterns, unmatched_findings)
        """

        matched = []
        unmatched = []

        for finding in findings:
            # Try to find a matching pattern
            pattern = self._find_matching_pattern(
                check_id=finding.check_id,
                target_pattern=target_pattern,
            )

            if pattern is None:
                # No pattern matches this finding
                unmatched.append(finding)
                continue

            # Check if this pattern is allowed by the mode
            if not self._is_pattern_allowed(pattern, mode):
                # Pattern exists but is too risky for current mode
                unmatched.append(finding)
                continue

            # Pattern matches and is allowed!
            matched.append(
                MatchedPattern(
                    finding=finding,
                    pattern=pattern,
                    confidence=pattern.confidence,
                    risk_level=pattern.risk_level,
                )
            )

        return matched, unmatched

    def _find_matching_pattern(
        self,
        check_id: str,
        target_pattern: str | None,
    ):
        """
        Find pattern that matches this check_id.

        Args:
            check_id: The check_id from audit finding
            target_pattern: Optional filter

        Returns:
            AutoFixablePattern or None
        """

        for pattern in self.patterns:
            # Check if pattern matches
            if pattern.check_id_pattern == check_id:
                # Exact match
                if target_pattern is None or pattern.check_id_pattern == target_pattern:
                    return pattern

            # Support wildcard matching (e.g., "style.*")
            if pattern.check_id_pattern.endswith("*"):
                prefix = pattern.check_id_pattern[:-1]
                if check_id.startswith(prefix):
                    if target_pattern is None or check_id.startswith(
                        target_pattern.replace("*", "")
                    ):
                        return pattern

        return None

    def _is_pattern_allowed(self, pattern, mode: RemediationMode) -> bool:
        """
        Check if pattern is allowed under current mode.

        Args:
            pattern: AutoFixablePattern to check
            mode: Current remediation mode

        Returns:
            True if pattern is allowed
        """

        if mode == RemediationMode.SAFE_ONLY:
            # Only high confidence + low risk
            return pattern.confidence >= 0.85 and pattern.risk_level == "low"

        elif mode == RemediationMode.MEDIUM_RISK:
            # Medium confidence + low/medium risk
            return pattern.confidence >= 0.70 and pattern.risk_level in [
                "low",
                "medium",
            ]

        elif mode == RemediationMode.ALL_DETERMINISTIC:
            # All deterministic patterns
            # (In future: exclude patterns that use LLM)
            return True

        return False

    async def _execute_fixes(
        self,
        matched: list[MatchedPattern],
        write: bool,
    ) -> list[FixDetail]:
        """
        Execute fixes for all matched patterns.

        Args:
            matched: List of matched patterns to fix
            write: Whether to actually apply fixes

        Returns:
            List of FixDetail records
        """

        fix_details = []

        for match in matched:
            start_ms = int(time.time() * 1000)

            # Get the handler for this pattern
            handler = self._get_handler(match.pattern.action_handler)

            if handler is None:
                # Handler not implemented yet
                logger.warning(
                    "Handler not found: %s (skipping)",
                    match.pattern.action_handler,
                )

                fix_details.append(
                    FixDetail(
                        finding_id=match.finding.check_id,
                        file_path=match.finding.file_path or "unknown",
                        action_handler=match.pattern.action_handler,
                        status="skipped",
                        error_message="Handler not implemented",
                        duration_ms=0,
                    )
                )
                continue

            # Execute the handler
            try:
                result: FixResult = await handler(
                    finding=match.finding,
                    file_handler=self.file_handler,
                    repo_root=self.repo_root,
                    write=write,
                )

                duration_ms = int(time.time() * 1000) - start_ms

                fix_details.append(
                    FixDetail(
                        finding_id=match.finding.check_id,
                        file_path=match.finding.file_path or "unknown",
                        action_handler=match.pattern.action_handler,
                        status="success" if result.ok else "failed",
                        error_message=result.error_message,
                        duration_ms=duration_ms,
                    )
                )

            except Exception as e:
                logger.error(
                    "Handler crashed: %s - %s", match.pattern.action_handler, e
                )
                duration_ms = int(time.time() * 1000) - start_ms

                fix_details.append(
                    FixDetail(
                        finding_id=match.finding.check_id,
                        file_path=match.finding.file_path or "unknown",
                        action_handler=match.pattern.action_handler,
                        status="failed",
                        error_message=f"Exception: {e!s}",
                        duration_ms=duration_ms,
                    )
                )

        return fix_details

    def _get_handler(self, action_handler: str):
        """
        Get the fix handler function by name.

        Args:
            action_handler: Handler name (e.g., "sort_imports")

        Returns:
            Handler function or None
        """

        # Map handler names to actual functions
        # For now, we only have one handler
        if action_handler == "sort_imports":
            from features.self_healing.handlers.import_sorting_handler import (
                sort_imports_handler,
            )

            return sort_imports_handler

        # Handler not found
        return None

    async def _validate_improvement(
        self,
        findings_before_count: int,
    ) -> tuple[bool, int, Path | None]:
        """
        Re-run audit to validate improvement.

        Args:
            findings_before_count: How many findings we started with

        Returns:
            Tuple of (validation_passed, findings_after_count, audit_path)
        """

        logger.info("Running validation audit...")

        try:
            # Run a fresh audit
            # This calls the constitutional auditor
            findings_after = await self.auditor.audit()

            # Count findings
            findings_after_count = len(findings_after)

            # Calculate improvement
            improvement = findings_before_count - findings_after_count

            # We pass validation if we reduced findings
            passed = improvement > 0

            # The audit writes to reports/audit_findings.json
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
            # If validation fails, we assume no improvement
            return False, findings_before_count, None

    async def _write_evidence(
        self,
        result: RemediationResult,
    ) -> Path:
        """
        Write evidence artifact to reports/remediation/.

        Args:
            result: The RemediationResult to save

        Returns:
            Path where evidence was written
        """

        # Create remediation directory if needed
        remediation_dir = self.repo_root / "reports" / "remediation"
        remediation_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"remediation_{timestamp}.json"

        evidence_path = remediation_dir / filename
        latest_path = remediation_dir / "latest_remediation.json"

        # Convert result to dict for JSON serialization
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

        # Write evidence file
        evidence_json = json.dumps(evidence, indent=2)

        # Use FileHandler for constitutional compliance
        rel_path = str(evidence_path.relative_to(self.repo_root))
        self.file_handler.write_runtime_json(rel_path, evidence)

        # Also write as "latest" for easy access
        rel_latest = str(latest_path.relative_to(self.repo_root))
        self.file_handler.write_runtime_json(rel_latest, evidence)

        logger.info("Evidence written to: %s", evidence_path)

        return evidence_path

    def _count_by_severity(
        self,
        findings: list[AuditFinding],
    ) -> dict[str, int]:
        """
        Count findings by severity level.

        Args:
            findings: List of findings

        Returns:
            Dict of {"error": N, "warning": N, "info": N}
        """

        counts = {"error": 0, "warning": 0, "info": 0}

        for finding in findings:
            severity_str = str(finding.severity)
            if severity_str in counts:
                counts[severity_str] += 1

        return counts
