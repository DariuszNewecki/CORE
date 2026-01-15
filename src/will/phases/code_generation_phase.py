# src/will/phases/code_generation_phase.py
# ID: will.phases.code_generation_phase

"""
Code Generation Phase Implementation

Generates production code based on approved plan.
Delegates to SpecificationAgent for actual code generation.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from shared.logger import getLogger
from shared.models.workflow_models import PhaseResult
from will.agents.coder_agent import CoderAgent
from will.agents.specification_agent import SpecificationAgent
from will.orchestration.decision_tracer import DecisionTracer
from will.orchestration.prompt_pipeline import PromptPipeline


if TYPE_CHECKING:
    from shared.context import CoreContext
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)


# ID: 3c4d5e6f-7g8h-9i0j-1k2l-3m4n5o6p7q8r
# ID: c8339686-813d-465c-829b-a7f7459fdc38
class CodeGenerationPhase:
    """
    Code generation phase.

    Takes execution plan from planning phase and generates actual code.
    Delegates to SpecificationAgent -> CoderAgent pipeline.
    """

    def __init__(self, core_context: CoreContext):
        self.context = core_context
        self.tracer = DecisionTracer()

    # ID: f3933e6c-6fc3-41e4-bb38-8c4e0bc80b0a
    async def execute(self, context: WorkflowContext) -> PhaseResult:
        """Execute code generation phase"""
        start = time.time()

        try:
            # Get plan from planning phase
            plan = context.results.get("planning", {}).get("execution_plan")

            if not plan:
                return PhaseResult(
                    name="code_generation",
                    ok=False,
                    error="No execution plan found from planning phase",
                    duration_sec=time.time() - start,
                )

            logger.info("🔧 Generating code for %d steps...", len(plan))

            # Initialize agents
            prompt_pipeline = PromptPipeline(self.context.git_service.repo_path)

            coder_agent = CoderAgent(
                cognitive_service=self.context.cognitive_service,
                prompt_pipeline=prompt_pipeline,
                auditor_context=self.context.auditor_context,
                qdrant_service=None,  # Optional semantic features
                context_service=None,  # Optional context enrichment
            )

            spec_agent = SpecificationAgent(
                coder_agent=coder_agent,
                context_str="",  # Could inject reconnaissance report
            )

            # Generate detailed plan with code
            detailed_plan = await spec_agent.elaborate_plan(
                goal=context.goal,
                plan=plan,
            )

            # Check for generation failures
            failed_steps = [
                step
                for step in detailed_plan.steps
                if step.metadata.get("generation_failed", False)
            ]

            if failed_steps:
                error_summary = "; ".join(
                    step.metadata.get("error", "unknown") for step in failed_steps
                )
                logger.warning(
                    "⚠️  %d/%d steps failed generation: %s",
                    len(failed_steps),
                    len(detailed_plan.steps),
                    error_summary,
                )

            # Trace decision
            self.tracer.record(
                agent="CodeGenerationPhase",
                decision_type="code_generated",
                rationale=f"Generated code for {len(detailed_plan.steps)} steps",
                chosen_action=f"DetailedPlan with {len(detailed_plan.steps) - len(failed_steps)} successful steps",
                context={
                    "total_steps": len(detailed_plan.steps),
                    "failed_steps": len(failed_steps),
                    "success_rate": (len(detailed_plan.steps) - len(failed_steps))
                    / len(detailed_plan.steps),
                },
            )

            duration = time.time() - start

            # Consider it successful if at least 80% of steps succeeded
            success_threshold = 0.8
            success_rate = (len(detailed_plan.steps) - len(failed_steps)) / len(
                detailed_plan.steps
            )

            return PhaseResult(
                name="code_generation",
                ok=success_rate >= success_threshold,
                data={
                    "detailed_plan": detailed_plan,
                    "total_steps": len(detailed_plan.steps),
                    "failed_steps": len(failed_steps),
                    "success_rate": success_rate,
                },
                error=(
                    ""
                    if success_rate >= success_threshold
                    else f"Only {success_rate:.0%} of steps succeeded (threshold: {success_threshold:.0%})"
                ),
                duration_sec=duration,
            )

        except Exception as e:
            logger.error("Code generation failed: %s", e, exc_info=True)
            duration = time.time() - start

            return PhaseResult(
                name="code_generation",
                ok=False,
                error=str(e),
                duration_sec=duration,
            )
