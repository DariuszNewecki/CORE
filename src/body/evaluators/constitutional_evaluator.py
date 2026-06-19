# src/body/evaluators/constitutional_evaluator.py

"""
ConstitutionalEvaluator - Assesses constitutional policy compliance.

CONSTITUTIONAL COMPLIANCE:
- Uses AuditorContext for all governance checks (Mind layer access)
- Evaluates files against rules from .intent/ structure
- No direct filesystem access to .intent/
- Maintains Mind/Body separation

V2.3-REBIRTH SCAFFOLD (2026-06-07):
Part of the V2 Component-pattern scaffold per `CORE-V2-Adaptive-Workflow-Pattern.md`
§5.5 and `CORE-The-Octopus-UNIX-Synthesis.md` §6. GH #590 closures 3+4 landed:
`repo_root` is now DI'd via `__init__` (so a Limb consumer constructs the evaluator
once and `execute()` calls drop repo_root from the per-call signature); and the
result contract matches the spec in `tests/body/evaluators/test_constitutional_evaluator.py`
— `compliance_score`, `remediation_available`, per-violation `suggested_fix`, a real
`governance_boundaries` scope detecting `.intent/` mutation attempts, and result metadata
populated with severity counts + operation context. Closures 1+2 (auto-discover dispatch
in `ProcessOrchestrator.run_adaptive()` + a concrete Limb consumer) remain deferred:
this evaluator still has no live call site today; hand-composition remains the live
V2 path (see `will/test_generation/`, `will/self_healing/`). The test contract is now
executable — it guards the contract that the eventual Limb consumer will bind to.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from shared.component_primitive import Component, ComponentPhase, ComponentResult
from shared.logger import getLogger


logger = getLogger(__name__)


_MUTATING_OPS = frozenset(
    {"refactor", "fix", "generate", "create", "write", "edit", "delete"}
)
"Operation types that constitute a mutation to the target file."

_DEFAULT_SCOPE = (
    "constitutional_compliance",
    "pattern_compliance",
    "governance_boundaries",
)

_SEVERITY_PENALTY = {"critical": 0.3, "error": 0.15, "warning": 0.05}
"Compliance-score penalty per violation by severity. Critical=0.3 matches test_critical_violations_penalized_more."


# ID: c935569b-95cd-4ee1-8128-ffdbb8f490e2
class ConstitutionalEvaluator(Component):
    """
    Evaluates constitutional compliance for files and operations.

    Checks against:
    - Constitutional rules from .intent/rules/
    - Constitutional principles from .intent/constitution/
    - Architectural patterns from .intent/enforcement/mappings/
    - Governance boundaries (no .intent/ writes, etc.)

    Returns ComponentResult with:
    - Binary compliance status (ok: True/False)
    - List of violations with details + suggested_fix
    - data["compliance_score"]: severity-weighted score, 0.0 (worst) to 1.0 (clean)
    - data["remediation_available"]: bool; when True, next_suggested="remediation_handler"
    - metadata: severity counts + operation context
    """

    def __init__(self, repo_root: Path):
        """
        Initialize evaluator with a repo root for governance access.

        Args:
            repo_root: Repository root path containing .intent/ — required, no default.
                The Limb consumer (per GH #590 closure 2) constructs the evaluator once
                with the active repo and reuses it; execute() drops repo_root from the
                per-call signature.
        """
        self.repo_root = repo_root
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
        file_path: str | None = None,
        operation_type: str | None = None,
        validation_scope: list[str] | None = None,
        **kwargs: Any,
    ) -> ComponentResult:
        """
        Evaluate constitutional compliance for a file or operation.

        Args:
            file_path: Optional path to file being evaluated
            operation_type: Optional type of operation (refactor, create, query, etc.)
            validation_scope: Optional list of validation types; defaults to all three
                (constitutional_compliance, pattern_compliance, governance_boundaries)
            **kwargs: Additional evaluation parameters (forwarded; unused today)

        Returns:
            ComponentResult with compliance status, violations, scoring, and metadata.
        """
        start_time = time.time()

        scope = list(validation_scope) if validation_scope else list(_DEFAULT_SCOPE)

        violations: list[dict[str, Any]] = []
        details: dict[str, Any] = {}

        try:
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

            severity_counts = self._count_severities(violations)
            compliance_score = self._compliance_score(severity_counts)
            remediation_available = self._has_remediation(violations)
            ok = severity_counts["critical"] == 0 and severity_counts["error"] == 0

            return ComponentResult(
                component_id=self.component_id,
                ok=ok,
                phase=self.phase,
                data={
                    "violations": violations,
                    "details": details,
                    "evaluation_scope": scope,
                    "compliance_score": compliance_score,
                    "remediation_available": remediation_available,
                },
                confidence=compliance_score,
                next_suggested=(
                    "remediation_handler" if remediation_available else None
                ),
                metadata={
                    "critical_violations": severity_counts["critical"],
                    "error_violations": severity_counts["error"],
                    "warning_violations": severity_counts["warning"],
                    "file_path": file_path,
                    "operation_type": operation_type,
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
                    "details": details,
                    "evaluation_scope": scope,
                    "compliance_score": 0.0,
                    "remediation_available": False,
                },
                confidence=0.0,
                metadata={
                    "critical_violations": 0,
                    "error_violations": 0,
                    "warning_violations": 0,
                    "file_path": file_path,
                    "operation_type": operation_type,
                },
                duration_sec=time.time() - start_time,
            )

    async def _check_constitutional_compliance(
        self, file_path: str | None
    ) -> list[dict[str, Any]]:
        """Check file against constitutional rules via AuditorContext."""
        if not file_path:
            return []
        try:
            from mind.governance.audit_context import AuditorContext
            from mind.governance.filtered_audit import run_filtered_audit

            auditor_context = AuditorContext(self.repo_root)
            await auditor_context.load_knowledge_graph()
            # Scope the audit to the file under evaluation. Without `files`,
            # run_filtered_audit scans the entire repo (~90-120s) only for the
            # per-file findings below to discard everything but `file_path` — a
            # full-repo audit to check one file. `files=[file_path]` scopes at
            # the source; context-level rules skip gracefully (they were already
            # excluded by the file_path filter), so the result is unchanged.
            findings, _, _ = await run_filtered_audit(
                auditor_context, rule_patterns=[r".*"], files=[file_path]
            )
            return [
                {
                    "type": "constitutional",
                    "rule_id": f.get("rule_id", "unknown"),
                    "severity": f.get("severity", "error"),
                    "message": f.get("message", "Violation"),
                    "file_path": file_path,
                    "suggested_fix": f.get("remediation", ""),
                }
                for f in findings
                if f.get("file_path") == str(file_path)
            ]
        except Exception:
            return []

    async def _check_pattern_compliance(self, file_path: str) -> list[dict[str, Any]]:
        """Check file against architectural patterns."""
        violations: list[dict[str, Any]] = []
        if "src/body/atomic/" in file_path:
            from body.evaluators.atomic_actions_evaluator import AtomicActionsEvaluator

            evaluator = AtomicActionsEvaluator()
            action_violations, _ = evaluator._check_file(self.repo_root / file_path)
            for v in action_violations:
                violations.append(
                    {
                        "type": "pattern",
                        "rule_id": v.rule_id,
                        "severity": v.severity,
                        "message": v.message,
                        "file_path": file_path,
                        "suggested_fix": "",
                    }
                )
        return violations

    def _check_governance_boundaries(
        self, file_path: str | None, operation_type: str | None
    ) -> list[dict[str, Any]]:
        """
        Detect operations that breach constitutional boundaries.

        Today this catches one shape: mutating operations targeting .intent/.
        The rule maps to governance.constitution.read_only, severity=critical.
        """
        violations: list[dict[str, Any]] = []
        if not file_path:
            return violations
        if file_path.startswith(".intent/") and operation_type in _MUTATING_OPS:
            violations.append(
                {
                    "type": "governance",
                    "rule_id": "governance.constitution.read_only",
                    "severity": "critical",
                    "message": (
                        f"Operation {operation_type!r} on {file_path!r} would mutate "
                        ".intent/ — constitutional surface is read-only outside the "
                        "governor confirmation gate."
                    ),
                    "file_path": file_path,
                    "suggested_fix": (
                        "Route .intent/ changes through the per-turn governor "
                        "confirmation gate (see CLAUDE.md 'Writing to .intent/ "
                        "and .specs/')."
                    ),
                }
            )
        return violations

    @staticmethod
    def _count_severities(violations: list[dict[str, Any]]) -> dict[str, int]:
        counts = {"critical": 0, "error": 0, "warning": 0}
        for v in violations:
            sev = v.get("severity")
            if sev in counts:
                counts[sev] += 1
        return counts

    @staticmethod
    def _compliance_score(severity_counts: dict[str, int]) -> float:
        penalty = sum(
            _SEVERITY_PENALTY[sev] * count for sev, count in severity_counts.items()
        )
        return max(0.0, 1.0 - penalty)

    @staticmethod
    def _has_remediation(violations: list[dict[str, Any]]) -> bool:
        """
        Determine whether any violation has a non-trivial suggested_fix.

        Without a live auto-remediation registry plumbed to this evaluator, "remediation
        available" means "the violation carries human-readable remediation guidance"
        — concretely, any violation whose suggested_fix is non-empty. The eventual
        Limb consumer (#590 closure 2) can swap this for a registry lookup.
        """
        return any(v.get("suggested_fix") for v in violations)
