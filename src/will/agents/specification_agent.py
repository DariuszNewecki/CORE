# src/will/agents/specification_agent.py
# ID: will.agents.specification

"""
SpecificationAgent - The Engineer

Transforms conceptual plans (from PlannerAgent) into executable specifications
with generated code. This is the "engineering" phase of autonomous workflows.

A3 UPDATE (Phase 5):
- Now handles "Trial Evidence" feedback to support the A3 retry loop.
- Consolidates code generation logic before any execution occurs.
- Strictly separates reasoning (Will) from staging (Crate) and finality (Body).

UNIX Philosophy:
- Does ONE thing: Generates precise, validated code specifications.
- Does NOT plan (delegates to PlannerAgent).
- Does NOT execute (delegates to ExecutionAgent).

Constitutional Alignment:
- Headless: Uses standard logging only (LOG-001 compliant).
- Traceable: All generation decisions recorded via DecisionTracer.
- Safe-by-Default: Validates code via CoderAgent's internal pipeline.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from shared.config import settings
from shared.logger import getLogger
from shared.models import ExecutionTask
from shared.models.workflow_models import DetailedPlan, DetailedPlanStep
from will.orchestration.decision_tracer import DecisionTracer


if TYPE_CHECKING:
    from will.agents.coder_agent import CoderAgent

logger = getLogger(__name__)


# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
class SpecificationAgent:
    """
    The Engineer: Turns architectural plans into detailed code specifications.
    """

    def __init__(
        self,
        coder_agent: CoderAgent,
        context_str: str = "",
    ):
        """
        Initialize the SpecificationAgent.

        Args:
            coder_agent: The CoderAgent used for LLM reasoning.
            context_str: Initial context (e.g., from reconnaissance).
        """
        self.coder = coder_agent
        self.context_str = context_str
        self.tracer = DecisionTracer()
        self.repo_root = settings.REPO_PATH

        logger.info("SpecificationAgent initialized (A3 Specialist Mode)")

    # ID: b2c3d4e5-f678-90ab-cdef-0123456789ab
    async def elaborate_plan(
        self,
        goal: str,
        plan: list[ExecutionTask],
    ) -> DetailedPlan:
        """
        Transforms conceptual plan into a detailed plan with validated code.

        This method iterates through the conceptual steps and fills in the
        actual implementation code, ensuring everything is ready for the
        Packaging (Crate) and Trial (Canary) phases.
        """
        start_time = time.time()

        if not plan:
            raise ValueError("SpecificationAgent: Cannot elaborate an empty plan.")

        logger.info(
            "🔧 Engineering Phase: Generating specifications for %d steps...", len(plan)
        )

        detailed_steps: list[DetailedPlanStep] = []
        code_generated_count = 0

        for i, task in enumerate(plan, 1):
            logger.info(
                "  Step %d/%d: %s (action=%s)", i, len(plan), task.step, task.action
            )

            # Internal generation logic
            detailed_step = await self._generate_specification(
                task, goal, step_number=i
            )

            if "code" in detailed_step.params:
                code_generated_count += 1

            detailed_steps.append(detailed_step)

        duration = time.time() - start_time

        logger.info(
            "✅ Engineering complete: %d steps, %d with code (%.2fs)",
            len(detailed_steps),
            code_generated_count,
            duration,
        )

        # Log the engineering decision for auditability
        self.tracer.record(
            agent="SpecificationAgent",
            decision_type="plan_elaboration",
            rationale=f"Generated specs for {len(plan)} steps",
            chosen_action=f"DetailedPlan with {code_generated_count} code blocks",
            context={
                "goal": goal,
                "total_steps": len(plan),
                "code_count": code_generated_count,
                "duration": duration,
            },
            confidence=0.9,
        )

        return DetailedPlan(
            goal=goal,
            steps=detailed_steps,
            metadata={
                "engineering_duration_sec": duration,
                "code_generated_count": code_generated_count,
                "total_steps": len(plan),
            },
        )

    # ID: c3d4e5f6-789a-bcde-f012-3456789abcde
    async def _generate_specification(
        self,
        task: ExecutionTask,
        goal: str,
        step_number: int,
    ) -> DetailedPlanStep:
        """Generates the actual code for a single step if required."""

        # 1. Check if this action actually needs LLM-generated code
        if not self._step_needs_code_generation(task):
            # Pass-through for non-code actions (e.g., sync.db, file.read, delete)
            return DetailedPlanStep.from_execution_task(task)

        # 2. Invoke the CoderAgent for reasoning
        logger.info("    → [Step %d] Generating code payload...", step_number)

        try:
            # Delegate to CoderAgent (Will layer)
            # Note: self.context_str includes any trial feedback from previous loop iterations!
            validated_code = await self.coder.generate_and_validate_code_for_task(
                task=task,
                high_level_goal=goal,
                context_str=self.context_str,
            )

            # Return the step enriched with the code blueprint
            return DetailedPlanStep.from_execution_task(task=task, code=validated_code)

        except Exception as e:
            logger.error("    → ❌ Step %d generation failed: %s", step_number, e)

            # Record the failure for tracing
            self.tracer.record(
                agent="SpecificationAgent",
                decision_type="step_generation_failure",
                rationale=str(e),
                chosen_action="Continue with failure metadata",
                confidence=0.0,
            )

            # Return a step marked as failed so the Orchestrator can decide whether to retry
            step = DetailedPlanStep.from_execution_task(task)
            step.metadata["generation_failed"] = True
            step.metadata["error"] = str(e)
            return step

    # ID: d4e5f678-9abc-def0-1234-56789abcdef0
    def _step_needs_code_generation(self, task: ExecutionTask) -> bool:
        """Rules defining which atomic actions require an LLM-generated payload."""
        code_actions = {"file.create", "file.edit", "create_file", "edit_file"}

        # Needs generation only if it's a code action AND the code isn't already in the plan
        return task.action in code_actions and task.params.code is None

    # ID: e5f67890-abcd-ef01-2345-6789abcdef01
    def update_context(self, additional_context: str) -> None:
        """
        Enriches the engineer's dossier with new information.
        Used primarily to inject failure evidence from the Canary Trial (Phase 3).
        """
        if additional_context:
            # Format as an urgent instruction so the LLM prioritizes fixing the error
            feedback_block = (
                "\n\n"
                "### 🚨 CRITICAL FEEDBACK FROM PREVIOUS ATTEMPT\n"
                "The previous code generation failed validation in the sandbox.\n"
                "USE THE EVIDENCE BELOW TO CORRECT YOUR LOGIC:\n"
                "--------------------------------------------------\n"
                f"{additional_context}\n"
                "--------------------------------------------------\n"
                "### END FEEDBACK\n"
            )
            self.context_str += feedback_block
            logger.info("SpecificationAgent: Dossier enriched with trial feedback.")

    # ID: 5fac0b78-4256-42a4-9208-01c3d5736a79
    def get_decision_trace(self) -> str:
        return self.tracer.format_trace()

    # ID: d5dfd350-85da-4860-83db-09f148b976d3
    def save_decision_trace(self) -> None:
        self.tracer.save_trace()
