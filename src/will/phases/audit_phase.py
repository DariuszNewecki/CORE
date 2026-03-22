# src/will/phases/audit_phase.py

"""
Audit Phase - Constitutional composite.

Routes to the correct validation sub-implementations based on workflow_type.
Audit is the only constitutional phase authorised to determine compliance.

Routing:
  refactor_modularity      → CanaryValidationPhase + StyleCheckPhase
  coverage_remediation     → SandboxValidationPhase
  full_feature_development → CanaryValidationPhase + SandboxValidationPhase
                             + StyleCheckPhase

Blocking semantics per sub-phase:
  CanaryValidationPhase  — import integrity gate is BLOCKING;
                           test failures are ADVISORY
  SandboxValidationPhase — test failures are ADVISORY (phase returns ok=True)
  StyleCheckPhase        — style errors are BLOCKING; warnings are advisory
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from shared.logger import getLogger
from shared.models.workflow_models import PhaseResult
from will.phases.canary_validation_phase import CanaryValidationPhase
from will.phases.sandbox_validation_phase import SandboxValidationPhase
from will.phases.style_check_phase import StyleCheckPhase


if TYPE_CHECKING:
    from shared.context import CoreContext
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)

_WORKFLOW_ROUTING: dict[str, list[str]] = {
    "refactor_modularity": ["canary_validation", "style_check"],
    "coverage_remediation": ["sandbox_validation"],
    "full_feature_development": [
        "canary_validation",
        "sandbox_validation",
        "style_check",
    ],
}


# ID: audit-phase-composite
# ID: cc4b82ff-08c4-4b52-8fd8-73270e8724fd
class AuditPhase:
    """
    Constitutional Audit phase.

    Selects and executes the appropriate validation sub-phases for the
    active workflow type. Aggregates results and enforces blocking
    semantics: if any blocking sub-phase fails, the audit fails.

    Advisory failures (canary test failures, sandbox test failures) are
    recorded but do not block the workflow.
    """

    def __init__(self, core_context: CoreContext):
        self.context = core_context
        self._canary = CanaryValidationPhase(core_context)
        self._sandbox = SandboxValidationPhase(core_context)
        self._style = StyleCheckPhase(core_context)

    # ID: 21ea35a0-c9df-45de-9a49-15e2b58db713
    async def execute(self, context: WorkflowContext) -> PhaseResult:
        """Execute audit sub-phases for the active workflow."""
        start = time.time()

        workflow_type = context.workflow_type
        sub_phases = _WORKFLOW_ROUTING.get(
            workflow_type, ["canary_validation", "style_check"]
        )

        logger.info(
            "🔍 AUDIT: workflow=%s, sub-phases=%s",
            workflow_type,
            sub_phases,
        )

        aggregated_data: dict = {
            "audit_result_explicit": True,
            "rule_evaluation_complete": False,
        }
        advisory_failures: list[str] = []

        for sub_phase_name in sub_phases:
            if sub_phase_name == "canary_validation":
                result = await self._canary.execute(context)
            elif sub_phase_name == "sandbox_validation":
                result = await self._sandbox.execute(context)
            elif sub_phase_name == "style_check":
                result = await self._style.execute(context)
            else:
                logger.warning("Unknown audit sub-phase: %s — skipping", sub_phase_name)
                continue

            context.results[sub_phase_name] = result.data
            aggregated_data[sub_phase_name] = result.data

            if not result.ok:
                # Determine if this is a hard block or advisory
                import_failed = result.data.get("import_integrity_failed", False)
                is_style = sub_phase_name == "style_check"

                if import_failed or is_style:
                    # Hard block — import integrity and style errors are constitutional
                    logger.error(
                        "❌ AUDIT: sub-phase '%s' BLOCKED workflow: %s",
                        sub_phase_name,
                        result.error,
                    )
                    return PhaseResult(
                        name="audit",
                        ok=False,
                        error=f"{sub_phase_name} blocked: {result.error}",
                        data=aggregated_data,
                        duration_sec=time.time() - start,
                    )
                else:
                    # Advisory — record but continue
                    advisory_failures.append(sub_phase_name)
                    logger.warning(
                        "⚠️  AUDIT: sub-phase '%s' advisory failure: %s",
                        sub_phase_name,
                        result.error,
                    )
            else:
                logger.info("✅ AUDIT: sub-phase '%s' passed", sub_phase_name)

        aggregated_data["rule_evaluation_complete"] = True
        aggregated_data["advisory_failures"] = advisory_failures

        if advisory_failures:
            logger.warning(
                "⚠️  AUDIT: completed with advisory failures in: %s",
                advisory_failures,
            )
        else:
            logger.info("✅ AUDIT: all sub-phases passed")

        return PhaseResult(
            name="audit",
            ok=True,
            data=aggregated_data,
            duration_sec=time.time() - start,
        )
