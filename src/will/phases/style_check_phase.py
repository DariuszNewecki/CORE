# src/will/phases/style_check_phase.py
# ID: af60f378-c551-40fc-ba50-2cf9e2e90c91

"""
Style Check Phase Implementation

Validates generated code against project style standards.
Runs ruff, black, and constitutional auditing.

Constitutional Principle: Auto-fix deterministic issues
- Formatting is automatically corrected
- Import order is automatically corrected
- Constitutional violations block execution
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from shared.logger import getLogger
from shared.models.workflow_models import PhaseResult
from will.orchestration.decision_tracer import DecisionTracer
from will.orchestration.validation_pipeline import validate_code_async


if TYPE_CHECKING:
    from shared.context import CoreContext
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)


# ID: 8b81433c-c598-452a-a913-12063678e894
class StyleCheckPhase:
    """
    Style validation phase - ensures code quality.

    This phase validates generated code against:
    - Ruff linting rules
    - Black formatting standards
    - Constitutional requirements

    Most violations are auto-fixable and don't block execution.
    """

    def __init__(self, core_context: CoreContext):
        self.context = core_context
        self.tracer = DecisionTracer()

    # ID: 35731b53-2382-4832-9bcc-417d068cb866
    async def execute(self, context: WorkflowContext) -> PhaseResult:
        """Execute style check phase"""
        start = time.time()

        try:
            # Get generated code from code_generation phase
            code_gen_data = context.results.get("code_generation", {})
            steps = self._extract_steps(code_gen_data)
            if not steps:
                logger.info("No code to validate")
                return PhaseResult(
                    name="style_check",
                    ok=True,
                    data={"skipped": True, "reason": "no_code_generated"},
                    duration_sec=time.time() - start,
                )

            logger.info("🎨 Running style checks on generated code...")

            # Validate each generated file
            total_violations = 0
            total_warnings = 0
            validated_files = []
            errors = []

            for i, step in enumerate(steps, 1):
                params = self._get_step_params(step)
                file_path = self._get_param(params, "file_path")
                code = self._get_param(params, "code")

                if not code or not file_path:
                    logger.debug("Step %d skipped (no code or file_path)", i)
                    continue

                logger.debug("Step %d validating: %s", i, file_path)

                # Run validation pipeline (includes ruff, black, constitutional)
                val_result = await validate_code_async(
                    file_path,
                    code,
                    auditor_context=self.context.auditor_context,
                )

                validated_files.append(file_path)

                # Count violations
                violations = val_result.get("violations", [])
                error_count = sum(1 for v in violations if v.get("severity") == "error")
                warning_count = sum(
                    1 for v in violations if v.get("severity") == "warning"
                )

                total_violations += error_count
                total_warnings += warning_count

                # Track errors (constitutional violations)
                if val_result["status"] == "dirty":
                    errors.append(
                        {
                            "file": file_path,
                            "violations": violations,
                        }
                    )

                logger.debug(
                    "  %s: %d errors, %d warnings",
                    file_path,
                    error_count,
                    warning_count,
                )

            duration = time.time() - start

            # Trace decision
            self.tracer.record(
                agent="StyleCheckPhase",
                decision_type="style_validation",
                rationale=f"Validated {len(validated_files)} files against style standards",
                chosen_action="ruff_black_constitutional",
                context={
                    "files_checked": len(validated_files),
                    "violations": total_violations,
                    "warnings": total_warnings,
                },
                confidence=1.0 if total_violations == 0 else 0.5,
            )

            # Style violations are BLOCKING if they're errors
            if total_violations > 0:
                logger.error(
                    "❌ Style check failed: %d violations in %d files",
                    total_violations,
                    len(errors),
                )

                return PhaseResult(
                    name="style_check",
                    ok=False,
                    error=f"{total_violations} style violations found",
                    data={
                        "violations": total_violations,
                        "warnings": total_warnings,
                        "files_checked": len(validated_files),
                        "errors": errors,
                    },
                    duration_sec=duration,
                )
            else:
                logger.info(
                    "✅ Style check passed: %d files validated (%d warnings)",
                    len(validated_files),
                    total_warnings,
                )

                return PhaseResult(
                    name="style_check",
                    ok=True,
                    data={
                        "violations": 0,
                        "warnings": total_warnings,
                        "files_checked": len(validated_files),
                    },
                    duration_sec=duration,
                )

        except Exception as e:
            logger.error("Style check error: %s", e, exc_info=True)
            duration = time.time() - start

            return PhaseResult(
                name="style_check",
                ok=False,
                error=str(e),
                duration_sec=duration,
            )

    def _extract_steps(self, code_gen_data: dict[str, Any]) -> list[Any]:
        detailed_plan_dict = code_gen_data.get("detailed_plan_dict")
        if isinstance(detailed_plan_dict, dict):
            steps = detailed_plan_dict.get("steps")
            if isinstance(steps, list):
                return steps

        detailed_plan = code_gen_data.get("detailed_plan")
        steps = getattr(detailed_plan, "steps", None)
        if isinstance(steps, list):
            return steps

        return []

    def _get_step_params(self, step: Any) -> Any:
        if isinstance(step, dict):
            return step.get("params", {})
        return getattr(step, "params", {})

    def _get_param(self, params: Any, key: str) -> Any:
        if isinstance(params, dict):
            return params.get(key)
        return getattr(params, key, None)
