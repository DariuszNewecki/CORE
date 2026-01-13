# src/will/orchestration/workflow_orchestrator.py
# ID: will.orchestration.workflow

"""
AutonomousWorkflowOrchestrator - The General Contractor (A3 Specialist)

Orchestrates the complete A3 autonomous development loop:
1. Planning (PlannerAgent) -> Strategy
2. Engineering (SpecificationAgent) -> Code Generation (Blueprint)
3. Packaging (Crate Action) -> Immutable Transaction Staging
4. Trial (Crate Processor) -> Sandbox Audit (The Canary)
5. Feedback (Recursion) -> Error Analysis and Retry (Max 3)
6. Construction (ExecutionAgent) -> Production Application

CONSTITUTIONAL ALIGNMENT:
- Aligned with 'autonomy.tracing.mandatory' for all A3 decisions.
- Enforces the 'A3 Trial-and-Error' loop standard.
- Headless: Uses standard logging only.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from shared.action_types import ActionResult
from shared.logger import getLogger
from shared.models.workflow_models import ExecutionResults, WorkflowResult
from will.orchestration.decision_tracer import DecisionTracer


if TYPE_CHECKING:
    from will.agents.execution_agent import ExecutionAgent
    from will.agents.planner_agent import PlannerAgent
    from will.agents.specification_agent import SpecificationAgent

logger = getLogger(__name__)


# ID: a1b2c3d4-e5f6-7890-abcd-ef0123456789
class AutonomousWorkflowOrchestrator:
    """
    The General Contractor: Coordinates the A3 Trial-and-Error loop.
    """

    def __init__(
        self,
        planner: PlannerAgent,
        spec_agent: SpecificationAgent,
        exec_agent: ExecutionAgent,
        write: bool = False,
    ):
        """
        Initialize the orchestrator with specialist agents.
        """
        self.planner = planner
        self.spec_agent = spec_agent
        self.exec_agent = exec_agent
        self.write = write
        self.tracer = DecisionTracer()

        # Constitutional sync: Contractor's permission must match user intent.
        self.exec_agent.write = write

        logger.info(
            "AutonomousWorkflowOrchestrator initialized [A3 Mode | Write: %s]",
            self.write,
        )

    # ID: b2c3d4e5-f678-90ab-cdef-0123456789ab
    async def execute_autonomous_goal(
        self,
        goal: str,
        reconnaissance_report: str = "",
    ) -> WorkflowResult:
        """
        The A3 Loop: Plan -> (Spec -> Crate -> Canary -> Feedback) x3 -> Execute.
        """
        workflow_start_time = time.time()
        logger.info("=" * 80)
        logger.info("🚀 INITIATING A3 AUTONOMOUS WORKFLOW")
        logger.info("Goal: %s", goal)
        logger.info("=" * 80)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PHASE 1: ARCHITECTURE (Planning)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        logger.info("📐 PHASE 1: ARCHITECTURE (Planning)")
        try:
            plan = await self.planner.create_execution_plan(
                goal=goal,
                reconnaissance_report=reconnaissance_report,
            )
            logger.info("✅ Plan accepted with %d conceptual steps.", len(plan))
        except Exception as e:
            logger.error("❌ Planning failed: %s", e)
            return self._create_failed_workflow_result(
                goal, "planning", str(e), time.time() - workflow_start_time
            )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # THE TRIAL LOOP (The A3 "Trial & Feedback" Cycle)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        attempts = 0
        max_attempts = 3
        last_trial_feedback = ""
        final_blueprint = None

        while attempts < max_attempts:
            attempts += 1
            logger.info("")
            logger.info("🔄 A3 LOOP: ATTEMPT %d/%d", attempts, max_attempts)
            logger.info("-" * 80)

            # PHASE 2: ENGINEERING (Specification)
            try:
                # If we have feedback from a previous failed Canary trial, give it to the Engineer
                if last_trial_feedback:
                    self.spec_agent.update_context(last_trial_feedback)

                # Generate code for each step
                detailed_plan = await self.spec_agent.elaborate_plan(goal, plan)
                final_blueprint = detailed_plan
            except Exception as e:
                logger.error("❌ Engineering failed: %s", e)
                last_trial_feedback = f"Engineering Error: {e!s}"
                continue

            # PHASE 2.5: PACKAGING (Crate creation)
            # Collect files for the Canary to audit
            crate_id = await self._stage_in_crate(goal, final_blueprint)

            # If no files were generated, we skip the Canary and go straight to Execution
            if crate_id == "no_crate_required":
                logger.info("No code changes detected. Skipping Canary Trial.")
                break

            if not crate_id:
                logger.error("❌ Crate packaging failed.")
                last_trial_feedback = (
                    "Infrastructure Error: Failed to package Intent Crate."
                )
                continue

            # PHASE 3: THE TRIAL (Canary Sandbox)
            success, trial_report = await self._run_canary_trial(crate_id)

            if success:
                logger.info("✅ CANARY TRIAL PASSED.")
                self.tracer.record(
                    agent="Orchestrator",
                    decision_type="canary_verdict",
                    rationale="Blueprint passed all constitutional audits in sandbox.",
                    chosen_action="Proceed to Final Application",
                    confidence=1.0,
                )
                break
            else:
                logger.warning("❌ CANARY TRIAL FAILED.")
                # Store the audit findings as feedback for the next retry
                last_trial_feedback = (
                    f"### CANARY AUDIT FEEDBACK\n"
                    f"Your generated code failed validation in the sandbox with these errors:\n"
                    f"{trial_report}\n\n"
                    f"TASK: Fix the code and try again."
                )

                self.tracer.record(
                    agent="Orchestrator",
                    decision_type="retry_logic",
                    rationale="Canary trial detected constitutional violations.",
                    chosen_action="Retry Engineering with Trial Evidence",
                    context={"attempt": attempts, "violations": trial_report},
                    confidence=0.5,
                )

                if attempts == max_attempts:
                    logger.error("🛑 Max attempts reached. A3 Loop failed.")
                    return self._create_failed_workflow_result(
                        goal,
                        "engineering",
                        f"Failed after {max_attempts} attempts. Last evidence: {trial_report}",
                        time.time() - workflow_start_time,
                    )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PHASE 4: CONSTRUCTION (Execution)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        if final_blueprint is None:
            return self._create_failed_workflow_result(
                goal,
                "engineering",
                "Final blueprint missing",
                time.time() - workflow_start_time,
            )

        logger.info("")
        logger.info("🏗️ PHASE 4: CONSTRUCTION (Execution)")
        logger.info("-" * 80)

        try:
            # The Contractor applying the proven code to production
            execution_results = await self.exec_agent.execute_plan(final_blueprint)

            duration = time.time() - workflow_start_time

            return WorkflowResult(
                goal=goal,
                detailed_plan=final_blueprint,
                execution_results=execution_results,
                success=execution_results.all_succeeded(),
                total_duration_sec=duration,
                metadata={
                    "attempts": attempts,
                    "canary_validated": crate_id != "no_crate_required",
                    "final_status": "completed",
                },
            )

        except Exception as e:
            logger.error("❌ Final execution crashed: %s", e)
            return self._create_failed_workflow_result(
                goal, "execution", str(e), time.time() - workflow_start_time
            )

    async def _stage_in_crate(self, goal: str, detailed_plan: Any) -> str | None:
        """Packages generated code into a staging crate."""
        files = {}
        for step in detailed_plan.steps:
            # Safely extract file path and code content
            file_path = step.params.get("file_path")
            code = step.params.get("code")
            if file_path and code:
                files[file_path] = code

        if not files:
            return "no_crate_required"

        # Call the Body action to stage the crate
        result = await self.exec_agent.executor.execute(
            action_id="crate.create", write=True, intent=goal, payload_files=files
        )

        return result.data.get("crate_id") if result.ok else None

    async def _run_canary_trial(self, crate_id: str) -> tuple[bool, str]:
        """Runs the constitutional audit on the crate in a sandbox."""
        logger.info("🧪 Sandbox: Proving Crate '%s' safe...", crate_id)

        try:
            from body.services.crate_processing_service import CrateProcessingService

            processor = CrateProcessingService()

            # Execute the sandbox trial
            success, findings = await processor.validate_crate_by_id(crate_id)

            if success:
                return True, "Passed"

            # Format the findings into a readable string for the feedback loop
            error_details = " | ".join(
                [f"[{f.check_id}] {f.message}" for f in findings]
            )
            return False, error_details

        except Exception as e:
            return False, f"Trial System Error: {e!s}"

    def _create_failed_workflow_result(
        self, goal: str, phase: str, error: str, duration: float
    ) -> WorkflowResult:
        """Helper to create a failed workflow result."""
        from shared.models.workflow_models import DetailedPlan

        detailed_plan = DetailedPlan(goal=goal, steps=[], metadata={"failed_at": phase})
        fail_res = ActionResult(
            action_id="workflow.failure", ok=False, data={"error": error}
        )
        exec_results = ExecutionResults(
            steps=[fail_res], success_count=0, failure_count=1, total_duration_sec=0.0
        )

        return WorkflowResult(
            goal=goal,
            detailed_plan=detailed_plan,
            execution_results=exec_results,
            success=False,
            total_duration_sec=duration,
            metadata={"error": error, "failed_phase": phase},
        )

    # ID: b27ea6e8-673e-4058-a7e1-879c5e7ac0c2
    async def save_decision_trace(self) -> None:
        """Save the session's decision trace."""
        await self.tracer.save_trace()
