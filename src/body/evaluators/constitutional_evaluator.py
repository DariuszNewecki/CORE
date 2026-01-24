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
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from shared.component_primitive import Component, ComponentPhase, ComponentResult
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
class ConstitutionalEvaluator(Component):
    """
    Evaluates constitutional compliance for files and operations.
    """

    def __init__(self):
        """Initialize evaluator. Dependencies are lazy-loaded in execute()."""
        self._validator_service = None

    @property
    # ID: 2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e
    def phase(self) -> ComponentPhase:
        """ConstitutionalEvaluator operates in AUDIT phase."""
        return ComponentPhase.AUDIT

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
        repo_root: Path,
        file_path: str | None = None,
        operation_type: str | None = None,
        target_content: str | None = None,
        validation_scope: list[str] | None = None,
        **kwargs: Any,
    ) -> ComponentResult:
        """
        Evaluate constitutional compliance for a file or operation.

        Args:
            repo_root: Absolute path to the repository root (Required).
            file_path: Path to file being evaluated (repo-relative).
            operation_type: Type of operation (for governance checks).
            target_content: Optional code content to evaluate.
            validation_scope: Optional list of specific checks to run.
            **kwargs: Additional context.

        Returns:
            ComponentResult with compliance assessment.
        """
        start_time = time.time()

        # Initialize AuditorContext JIT with the provided repo_root
        from mind.governance.audit_context import AuditorContext

        auditor_context = AuditorContext(repo_root)

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
                    auditor_context, file_path
                )
                violations.extend(const_violations)
                details["constitutional"] = {
                    "checked": True,
                    "violations": len(const_violations),
                }

            if "pattern_compliance" in scope and file_path:
                pattern_violations = await self._check_pattern_compliance(
                    repo_root, file_path
                )
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

                # Deduct points per violation
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
        self, auditor_context: Any, file_path: str | None
    ) -> list[dict[str, Any]]:
        """
        Check file against constitutional rules using passed AuditorContext.
        """
        if not file_path:
            return []

        violations = []

        try:
            # Load knowledge graph if needed
            await auditor_context.load_knowledge_graph()

            # Run filtered audit for this file
            from mind.governance.filtered_audit import run_filtered_audit

            findings, _, _ = await run_filtered_audit(
                auditor_context, rule_patterns=[r".*"]
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
    async def _check_pattern_compliance(
        self, repo_root: Path, file_path: str
    ) -> list[dict[str, Any]]:
        """
        Check file against pattern rules (atomic actions, etc.).
        """
        violations = []

        try:
            # Check if file is atomic action
            if "src/body/atomic/" in file_path:
                # REFACTORED: Use V2 Evaluator instead of legacy checker
                from body.evaluators.atomic_actions_evaluator import (
                    AtomicActionsEvaluator,
                )

                evaluator = AtomicActionsEvaluator()
                abs_path = repo_root / file_path

                if abs_path.exists():
                    # Use internal check for single file analysis
                    action_violations, _ = evaluator._check_file(abs_path)

                    if action_violations:
                        for v in action_violations:
                            violations.append(
                                {
                                    "type": "pattern",
                                    "rule_id": v.rule_id,
                                    "severity": v.severity,
                                    "message": v.message,
                                    "file_path": file_path,
                                    "suggested_fix": v.suggested_fix
                                    or "Follow atomic actions contract",
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
        """Check if violations have automated remediation available."""
        remediable_types = [
            "constitutional",  # Header fixes, etc.
            "pattern",  # Pattern corrections
        ]

        return any(
            v.get("type") in remediable_types and v.get("suggested_fix")
            for v in violations
        )
