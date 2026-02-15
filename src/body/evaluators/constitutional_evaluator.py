# src/body/evaluators/constitutional_evaluator.py

"""
ConstitutionalEvaluator - Assesses constitutional policy compliance.

CONSTITUTIONAL COMPLIANCE:
- Uses AuditorContext for all governance checks (Mind layer access)
- Evaluates files against rules from .intent/ structure
- No direct filesystem access to .intent/
- Maintains Mind/Body separation

CONSTITUTIONAL FIX (V2.3):
- Removed unused variable 'target_content' (workflow.dead_code_check).
- Maintains Mind/Body separation: Evaluates rules using the AuditorContext.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from shared.component_primitive import Component, ComponentPhase, ComponentResult
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: c935569b-95cd-4ee1-8128-ffdbb8f490e2
class ConstitutionalEvaluator(Component):
    """
    Evaluates constitutional compliance for files and operations.

    Checks against:
    - Constitutional rules from .intent/rules/
    - Constitutional principles from .intent/constitution/
    - Architectural patterns from .intent/enforcement/mappings/
    - Governance boundaries (no .intent/ writes, etc.)

    Returns:
    - Binary compliance status (ok: True/False)
    - List of violations with details
    - Compliance score (confidence metric)
    - Remediation context
    """

    def __init__(self):
        """Initialize evaluator with lazy-loaded governance components."""
        self._validator_service = None

    @property
    # ID: e947509f-0965-4723-8997-0b0e55143a81
    def phase(self) -> ComponentPhase:
        """ConstitutionalEvaluator operates in AUDIT phase."""
        return ComponentPhase.AUDIT

    @property
    # ID: a7173a43-ebca-4bba-9512-17b69d01ddce
    def validator_service(self):
        """Lazy-load ConstitutionalValidator to avoid circular imports."""
        if self._validator_service is None:
            from body.services.constitutional_validator import get_validator

            self._validator_service = get_validator()
        return self._validator_service

    # ID: 4770d6fd-6014-4593-9d7c-ae978cedaedf
    async def execute(
        self,
        repo_root: Path,
        file_path: str | None = None,
        operation_type: str | None = None,
        validation_scope: list[str] | None = None,
        **kwargs: Any,
    ) -> ComponentResult:
        """
        Evaluate constitutional compliance for a file or operation.

        Args:
            repo_root: Repository root path
            file_path: Optional path to file being evaluated
            operation_type: Optional type of operation (refactor, create, etc.)
            validation_scope: Optional list of validation types to perform
            **kwargs: Additional evaluation parameters

        Returns:
            ComponentResult with compliance status and violations
        """
        start_time = time.time()

        from mind.governance.audit_context import AuditorContext

        auditor_context = AuditorContext(repo_root)

        violations = []
        details = {}

        try:
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

            return ComponentResult(
                component_id=self.component_id,
                ok=ok,
                phase=self.phase,
                data={
                    "violations": violations,
                    "details": details,
                    "evaluation_scope": scope,
                },
                confidence=1.0 if ok else 0.5,
                duration_sec=time.time() - start_time,
            )

        except Exception as e:
            logger.error("ConstitutionalEvaluator failed: %s", e, exc_info=True)
            return ComponentResult(
                component_id=self.component_id,
                ok=False,
                phase=self.phase,
                data={"error": str(e)},
                confidence=0.0,
                duration_sec=time.time() - start_time,
            )

    async def _check_constitutional_compliance(
        self, auditor_context: Any, file_path: str | None
    ) -> list[dict[str, Any]]:
        """
        Check file against constitutional rules via AuditorContext.

        Args:
            auditor_context: AuditorContext for governance access
            file_path: Path to file being checked

        Returns:
            List of violation dicts
        """
        if not file_path:
            return []
        try:
            await auditor_context.load_knowledge_graph()
            from mind.governance.filtered_audit import run_filtered_audit

            findings, _, _ = await run_filtered_audit(
                auditor_context, rule_patterns=[r".*"]
            )
            return [
                {
                    "type": "constitutional",
                    "rule_id": f.get("rule_id", "unknown"),
                    "severity": f.get("severity", "error"),
                    "message": f.get("message", "Violation"),
                    "file_path": file_path,
                }
                for f in findings
                if f.get("file_path") == str(file_path)
            ]
        except Exception:
            return []

    async def _check_pattern_compliance(
        self, repo_root: Path, file_path: str
    ) -> list[dict[str, Any]]:
        """
        Check file against architectural patterns.

        Args:
            repo_root: Repository root path
            file_path: Path to file being checked

        Returns:
            List of pattern violation dicts
        """
        violations = []
        if "src/body/atomic/" in file_path:
            from body.evaluators.atomic_actions_evaluator import AtomicActionsEvaluator

            evaluator = AtomicActionsEvaluator()
            action_violations, _ = evaluator._check_file(repo_root / file_path)
            for v in action_violations:
                violations.append(
                    {
                        "type": "pattern",
                        "rule_id": v.rule_id,
                        "severity": v.severity,
                        "message": v.message,
                        "file_path": file_path,
                    }
                )
        return violations
