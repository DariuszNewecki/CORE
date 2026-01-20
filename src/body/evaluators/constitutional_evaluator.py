# src/body/evaluators/constitutional_evaluator.py

"""
ConstitutionalEvaluator - Assesses constitutional policy compliance.

Constitutional Alignment:
- Phase: AUDIT (Quality assessment and pattern detection)
- Authority: POLICY (Enforces rules from .intent/ constitution)
- Purpose: Evaluate whether code/operations comply with governance policies
- Boundary: Read-only analysis, no mutations

This component EVALUATES constitutional compliance, does not ENFORCE it.
Enforcement happens in EXECUTION phase via FileHandler/IntentGuard.

Usage:
    evaluator = ConstitutionalEvaluator()
    result = await evaluator.execute(
        file_path="src/models/user.py",
        operation_type="refactor"
    )

    if not result.ok:
        print(f"Violations: {result.data['violations']}")
"""

from __future__ import annotations

import time
from typing import Any

from shared.component_primitive import Component, ComponentPhase, ComponentResult
from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
class ConstitutionalEvaluator(Component):
    """
    Evaluates constitutional compliance for files and operations.

    Checks against:
    - Constitutional principles (.intent/charter/constitution/)
    - Policy rules (.intent/charter/policies/)
    - Pattern compliance (.intent/charter/patterns/)
    - Governance boundaries (no .intent/ writes, etc.)

    Output provides:
    - Binary compliance status (ok: True/False)
    - List of violations with details
    - Compliance score (0.0-1.0)
    - Remediation suggestions
    """

    def __init__(self):
        """Initialize evaluator with lazy-loaded governance components."""
        self._auditor_context = None
        self._validator_service = None

    @property
    # ID: 2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e
    def phase(self) -> ComponentPhase:
        """ConstitutionalEvaluator operates in AUDIT phase."""
        return ComponentPhase.AUDIT

    @property
    # ID: 3c4d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f
    def auditor_context(self):
        """Lazy-load AuditorContext to avoid circular imports."""
        if self._auditor_context is None:
            from mind.governance.audit_context import AuditorContext

            self._auditor_context = AuditorContext(settings.REPO_PATH)
        return self._auditor_context

    @property
    # ID: 4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a
    def validator_service(self):
        """Lazy-load ConstitutionalValidator to avoid circular imports."""
        if self._validator_service is None:
            from body.services.constitutional_validator import get_validator

            self._validator_service = get_validator()
        return self._validator_service

    # ID: 5e6f7a8b-9c0d-1e2f-3a4b-5c6d7e8f9a0b
    async def execute(
        self,
        file_path: str | None = None,
        operation_type: str | None = None,
        target_content: str | None = None,
        validation_scope: list[str] | None = None,
        **kwargs: Any,
    ) -> ComponentResult:
        """
        Evaluate constitutional compliance for a file or operation.

        Args:
            file_path: Path to file being evaluated (repo-relative)
            operation_type: Type of operation (for governance checks)
            target_content: Optional code content to evaluate (if not from file)
            validation_scope: Optional list of specific checks to run
            **kwargs: Additional context

        Returns:
            ComponentResult with compliance assessment
        """
        start_time = time.time()

        # Initialize results
        violations = []
        compliance_score = 1.0
        details = {}

        try:
            # Run requested validation checks
            scope = validation_scope or [
                "constitutional_compliance",
                "pattern_compliance",
                "governance_boundaries",
            ]

            if "constitutional_compliance" in scope:
                const_violations = await self._check_constitutional_compliance(
                    file_path
                )
                violations.extend(const_violations)
                details["constitutional"] = {
                    "checked": True,
                    "violations": len(const_violations),
                }

            if "pattern_compliance" in scope and file_path:
                pattern_violations = await self._check_pattern_compliance(file_path)
                violations.extend(pattern_violations)
                details["patterns"] = {
                    "checked": True,
                    "violations": len(pattern_violations),
                }

            if "governance_boundaries" in scope:
                gov_violations = self._check_governance_boundaries(
                    file_path, operation_type
                )
                violations.extend(gov_violations)
                details["governance"] = {
                    "checked": True,
                    "violations": len(gov_violations),
                }

            # Calculate compliance score
            if violations:
                # Score penalty based on violation severity
                critical_count = sum(
                    1 for v in violations if v.get("severity") == "critical"
                )
                error_count = sum(1 for v in violations if v.get("severity") == "error")
                warning_count = sum(
                    1 for v in violations if v.get("severity") == "warning"
                )

                # Deduct points per violation (critical=0.3, error=0.2, warning=0.1)
                score_deduction = (
                    critical_count * 0.3 + error_count * 0.2 + warning_count * 0.1
                )
                compliance_score = max(0.0, 1.0 - score_deduction)

            # Determine if evaluation passes
            ok = (
                len(
                    [
                        v
                        for v in violations
                        if v.get("severity") in ["critical", "error"]
                    ]
                )
                == 0
            )

            logger.info(
                "ConstitutionalEvaluator: %s (score: %.2f, %d violations)",
                "PASS" if ok else "FAIL",
                compliance_score,
                len(violations),
            )

            return ComponentResult(
                component_id=self.component_id,
                ok=ok,
                phase=self.phase,
                data={
                    "violations": violations,
                    "compliance_score": compliance_score,
                    "details": details,
                    "evaluation_scope": scope,
                    "remediation_available": self._has_remediation(violations),
                },
                confidence=compliance_score,
                next_suggested="remediation_handler" if violations else None,
                metadata={
                    "file_path": file_path,
                    "operation_type": operation_type,
                    "critical_violations": sum(
                        1 for v in violations if v.get("severity") == "critical"
                    ),
                    "error_violations": sum(
                        1 for v in violations if v.get("severity") == "error"
                    ),
                    "warning_violations": sum(
                        1 for v in violations if v.get("severity") == "warning"
                    ),
                },
                duration_sec=time.time() - start_time,
            )

        except Exception as e:
            logger.error("ConstitutionalEvaluator failed: %s", e, exc_info=True)
            return ComponentResult(
                component_id=self.component_id,
                ok=False,
                phase=self.phase,
                data={
                    "error": str(e),
                    "violations": [],
                    "compliance_score": 0.0,
                },
                confidence=0.0,
                duration_sec=time.time() - start_time,
            )

    # ID: 6f7a8b9c-0d1e-2f3a-4b5c-6d7e8f9a0b1c
    async def _check_constitutional_compliance(
        self, file_path: str | None
    ) -> list[dict[str, Any]]:
        """
        Check file against constitutional rules using AuditorContext.

        Returns: List of violation dicts
        """
        if not file_path:
            return []

        violations = []

        try:
            # Load knowledge graph if needed
            await self.auditor_context.load_knowledge_graph()

            # Run filtered audit for this file
            from mind.governance.filtered_audit import run_filtered_audit

            findings, _, _ = await run_filtered_audit(
                self.auditor_context, rule_patterns=[r".*"]
            )

            # Filter to this file only
            file_violations = [
                f for f in findings if f.get("file_path") == str(file_path)
            ]

            # Convert to standard format
            for finding in file_violations:
                violations.append(
                    {
                        "type": "constitutional",
                        "rule_id": finding.get("rule_id", "unknown"),
                        "severity": finding.get("severity", "error"),
                        "message": finding.get("message", "Constitutional violation"),
                        "file_path": file_path,
                        "suggested_fix": finding.get("suggested_fix", ""),
                    }
                )

        except Exception as e:
            logger.warning(
                "Could not run constitutional audit for %s: %s", file_path, e
            )

        return violations

    # ID: 7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d
    async def _check_pattern_compliance(self, file_path: str) -> list[dict[str, Any]]:
        """
        Check file against pattern rules (atomic actions, etc.).

        Returns: List of violation dicts
        """
        violations = []

        try:
            # Check if file is atomic action
            if "src/body/atomic/" in file_path:
                # Verify atomic action pattern compliance
                from body.checkers.atomic_actions_checker import AtomicActionsChecker

                checker = AtomicActionsChecker()
                abs_path = settings.REPO_PATH / file_path

                if abs_path.exists():
                    check_result = await checker.check_file(abs_path)

                    if not check_result.passed:
                        for error in check_result.errors:
                            violations.append(
                                {
                                    "type": "pattern",
                                    "rule_id": "atomic_actions_pattern",
                                    "severity": "error",
                                    "message": error,
                                    "file_path": file_path,
                                    "suggested_fix": "Follow atomic actions contract",
                                }
                            )

        except Exception as e:
            logger.warning(
                "Could not check pattern compliance for %s: %s", file_path, e
            )

        return violations

    # ID: 8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e
    def _check_governance_boundaries(
        self, file_path: str | None, operation_type: str | None
    ) -> list[dict[str, Any]]:
        """
        Check for governance boundary violations.

        Returns: List of violation dicts
        """
        violations = []

        if not file_path:
            return violations

        # CRITICAL: Cannot write to .intent/ directory
        if file_path.startswith(".intent/"):
            violations.append(
                {
                    "type": "governance",
                    "rule_id": "governance.constitution.read_only",
                    "severity": "critical",
                    "message": "Constitutional intent directory is immutable",
                    "file_path": file_path,
                    "suggested_fix": "Propose constitutional change through proper channels",
                }
            )

        # Check operation permissions
        if operation_type and file_path:
            try:
                decision = self.validator_service.can_execute_autonomously(
                    file_path, operation_type
                )

                if not decision.allowed:
                    violations.append(
                        {
                            "type": "governance",
                            "rule_id": "governance.autonomous_operation",
                            "severity": "error",
                            "message": f"Operation not allowed: {decision.rationale}",
                            "file_path": file_path,
                            "suggested_fix": f"Required approval: {decision.approval_type.value}",
                        }
                    )

            except Exception as e:
                logger.warning(
                    "Could not check governance decision for %s: %s", file_path, e
                )

        return violations

    # ID: 9c0d1e2f-3a4b-5c6d-7e8f-9a0b1c2d3e4f
    def _has_remediation(self, violations: list[dict[str, Any]]) -> bool:
        """
        Check if violations have automated remediation available.

        Returns: True if any violation can be auto-fixed
        """
        remediable_types = [
            "constitutional",  # Header fixes, etc.
            "pattern",  # Pattern corrections
        ]

        return any(
            v.get("type") in remediable_types and v.get("suggested_fix")
            for v in violations
        )
