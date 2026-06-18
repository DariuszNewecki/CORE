# src/mind/logic/engines/workflow_gate/engine.py

"""
Workflow Gate Engine - Context-Aware Process Auditor.

CONSTITUTIONAL ALIGNMENT:
- Aligned with 'async.no_manual_loop_run'.
- Promoted to natively async to eliminate thread-based loop hijacking.
- Provides non-blocking verification for system-wide processes (Tests, Coverage).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from mind.logic.engines.base import BaseEngine, EngineResult, EvidenceClass
from mind.logic.engines.workflow_gate.base_check import (
    StructuredViolation,
    WorkflowCheck,
)
from mind.logic.engines.workflow_gate.checks import (
    AlignmentVerificationCheck,
    AuditHistoryCheck,
    CanaryDeploymentCheck,
    CoverageMinimumCheck,
    DeadCodeCheck,
    ImportResolutionCheck,
    LinterComplianceCheck,
    RuffFormatCheck,
    TestVerificationCheck,
)
from mind.logic.engines.workflow_gate.checks.quality import QualityGateCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity
from shared.path_resolver import PathResolver


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)


# ID: 170810a6-c446-41de-acf4-29defa345522
class WorkflowGateEngine(BaseEngine):
    """
    Process-Aware Governance Auditor.

    Orchestrates specialized workflow checks (bits) to verify that
    operational requirements (like test passing or coverage) are met.
    """

    engine_id = "workflow_gate"
    evidence_class = EvidenceClass.PROVEN  # ADR-113: deterministic verdict

    @classmethod
    # ID: 2b8e4f3d-1a9c-4b65-9d7e-3f8a1c5e2b04
    def is_context_level_for(cls, check_type: str | None) -> bool:
        """
        ADR-076 D1/D2: every workflow_gate check_type is context-level.

        All twelve checks (tests, coverage, canary, alignment, dead code,
        audit history, linter, imports, ruff format, mypy, security,
        pytest collection) walk system state rather than a single file_path.
        """
        return True

    def __init__(self, path_resolver: PathResolver) -> None:
        """Initialize the engine and register its specialized check logic."""
        check_instances: list[WorkflowCheck] = [
            TestVerificationCheck(),
            CoverageMinimumCheck(path_resolver),
            CanaryDeploymentCheck(),
            AlignmentVerificationCheck(path_resolver),
            DeadCodeCheck(path_resolver),
            AuditHistoryCheck(),
            LinterComplianceCheck(),
            ImportResolutionCheck(),
            RuffFormatCheck(),
            QualityGateCheck(
                path_resolver,
                "mypy_check",
                ["mypy", "src/", "--ignore-missing-imports"],
            ),
            QualityGateCheck(path_resolver, "security_check", ["pip-audit"]),
            QualityGateCheck(
                path_resolver,
                "pytest_check",
                ["pytest", "tests/", "-q", "--co"],
            ),  # Collection only for speed
        ]

        self._checks: dict[str, WorkflowCheck] = {
            check.check_type: check for check in check_instances
        }

        logger.debug(
            "WorkflowGateEngine initialized with %d check types: %s",
            len(self._checks),
            ", ".join(sorted(self._checks.keys())),
        )

    # ID: 9b12e3f4-c5d6-7e8f-9a0b-1c2d3e4f5a6b
    async def verify_context(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        """
        Executes a context-level check against system state.
        """
        check_type = params.get("check_type")
        if not check_type:
            return [
                AuditFinding(
                    check_id="workflow_gate.error",
                    severity=AuditSeverity.BLOCK,
                    message="Missing 'check_type' parameter in constitutional rule.",
                    file_path="none",
                )
            ]

        check_logic = self._checks.get(check_type)
        if not check_logic:
            return [
                AuditFinding(
                    check_id="workflow_gate.error",
                    severity=AuditSeverity.BLOCK,
                    message=f"Logic Error: Engine does not support check_type '{check_type}'",
                    file_path="none",
                )
            ]

        try:
            # Native await - no loop hijacking required
            violations = await check_logic.verify(None, params)

            findings = []
            for v in violations:
                # ADR-098 D1/D2: aggregate quality gates return one
                # StructuredViolation per affected file, carrying file_path
                # and structured occurrence context. The severity set here
                # is provisional — rule_executor overrides it from the
                # rule's declared enforcement (ADR-098 D4) for every
                # context-level finding before it reaches the report.
                if isinstance(v, StructuredViolation):
                    findings.append(
                        AuditFinding(
                            check_id=f"workflow.{check_type}",
                            severity=AuditSeverity.BLOCK,
                            message=v.message,
                            file_path=v.file_path,
                            context=v.context,
                        )
                    )
                elif v.endswith(".py"):
                    findings.append(
                        AuditFinding(
                            check_id=f"workflow.{check_type}",
                            severity=AuditSeverity.BLOCK,
                            message=f"File would be reformatted: {v}",
                            file_path=v,
                        )
                    )
                else:
                    findings.append(
                        AuditFinding(
                            check_id=f"workflow.{check_type}",
                            severity=AuditSeverity.BLOCK,
                            message=v,
                            file_path="System",
                        )
                    )
            return findings
        except Exception as e:
            logger.error("Workflow logic '%s' failed: %s", check_type, e, exc_info=True)
            return [
                AuditFinding(
                    check_id=f"workflow.{check_type}.error",
                    severity=AuditSeverity.BLOCK,
                    message=f"Internal Engine Error during {check_type} verification: {e}",
                    file_path="none",
                )
            ]

    # ID: 449a88ef-71ff-4f63-b692-4cffdc6483ce
    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        """
        Natively async verification.

        REFACTORED: Removed legacy thread-spawning and run_until_complete logic.
        This now properly participates in the system's async runtime.
        """
        return await self._verify_async(file_path, params)

    async def _verify_async(
        self, file_path: Path | None, params: dict[str, Any]
    ) -> EngineResult:
        """Internal async logic shared by verify and verify_context."""
        check_type = params.get("check_type")
        if not check_type:
            return EngineResult(
                False, "Missing check_type", ["No check_type provided"], self.engine_id
            )

        check = self._checks.get(check_type)
        if not check:
            return EngineResult(
                False,
                "Invalid check_type",
                [f"Unsupported: {check_type}"],
                self.engine_id,
            )

        try:
            violations = await check.verify(file_path, params)
            return EngineResult(
                ok=(not violations),
                message=(
                    "Workflow compliant"
                    if not violations
                    else "Workflow violations found"
                ),
                violations=violations,
                engine_id=self.engine_id,
            )
        except Exception as e:
            return EngineResult(False, f"Engine Error: {e}", [str(e)], self.engine_id)
