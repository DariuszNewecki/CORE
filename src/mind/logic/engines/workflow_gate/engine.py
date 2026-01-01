# src/mind/logic/engines/workflow_gate/engine.py

"""
Workflow Gate Engine - Context-Aware Process Auditor.

This engine enforces rules based on the outcomes of system-wide processes
(Tests, Coverage, Audits). It operates on the full AuditorContext to
verify compliance that cannot be determined by looking at a single file.

CONSTITUTIONAL ALIGNMENT:
- Aligns with 'standard_architecture_workflow_rules'.
- Implements 'verify_context' for dynamic rule execution.
- Headless execution using centralized logging.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from mind.logic.engines.base import BaseEngine, EngineResult
from mind.logic.engines.workflow_gate.base_check import WorkflowCheck
from mind.logic.engines.workflow_gate.checks import (
    AlignmentVerificationCheck,
    AuditHistoryCheck,
    CanaryDeploymentCheck,
    CoverageMinimumCheck,
    LinterComplianceCheck,
    TestVerificationCheck,
)
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


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

    def __init__(self) -> None:
        """Initialize the engine and register its specialized check logic."""
        # The 'bits' that perform the actual measurement
        check_instances: list[WorkflowCheck] = [
            TestVerificationCheck(),
            CoverageMinimumCheck(),
            CanaryDeploymentCheck(),
            AlignmentVerificationCheck(),
            AuditHistoryCheck(),
            LinterComplianceCheck(),
        ]

        # Map check_type strings from JSON to these implementations
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
        Required by the Dynamic Rule Executor for rules targeting the full Mind.
        """
        check_type = params.get("check_type")
        if not check_type:
            return [
                AuditFinding(
                    check_id="workflow_gate.error",
                    severity=AuditSeverity.ERROR,
                    message="Missing 'check_type' parameter in constitutional rule definition.",
                    file_path="none",
                )
            ]

        check_logic = self._checks.get(check_type)
        if not check_logic:
            return [
                AuditFinding(
                    check_id="workflow_gate.error",
                    severity=AuditSeverity.ERROR,
                    message=f"Logic Error: Engine does not support check_type '{check_type}'",
                    file_path="none",
                )
            ]

        try:
            # Execute the specific logic (e.g. check DB for test results)
            # file_path is None because we are operating on system context
            violations = await check_logic.verify(None, params)

            # Normalize raw strings into AuditFindings for the Auditor
            return [
                AuditFinding(
                    check_id=f"workflow.{check_type}",
                    severity=AuditSeverity.ERROR,
                    message=v,
                    file_path="System",
                )
                for v in violations
            ]
        except Exception as e:
            logger.error("Workflow logic '%s' failed: %s", check_type, e, exc_info=True)
            return [
                AuditFinding(
                    check_id=f"workflow.{check_type}.error",
                    severity=AuditSeverity.ERROR,
                    message=f"Internal Engine Error during {check_type} verification: {e}",
                    file_path="none",
                )
            ]

    # ID: 449a88ef-71ff-4f63-b692-4cffdc6483ce
    def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        """
        Sync wrapper for backward compatibility with file-level triggers.
        """
        import asyncio
        import threading

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            result = [None]
            exception = [None]

            # ID: c64858c6-a696-42f4-89a1-930bd12b136f
            def run_in_thread():
                try:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        coro = self._verify_async(file_path, params)
                        result[0] = new_loop.run_until_complete(coro)
                    finally:
                        new_loop.close()
                except Exception as ex:
                    exception[0] = ex

            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()

            if exception[0]:
                raise exception[0]
            return result[0]

        return asyncio.run(self._verify_async(file_path, params))

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
