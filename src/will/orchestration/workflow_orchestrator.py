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

UNIX Philosophy:
- Does ONE thing: Manages the lifecycle, retry logic, and phase transitions.
- Delegates all "Thinking" to Agents and all "Doing" to the Body.

Constitutional Alignment:
- A3 Maturity: Forbids direct writes; requires successful Canary Trial.
- Headless: No terminal UI; communicates via standard logger and ActionResults.
- Traceable: Every retry and trial failure is booked in the DecisionTracer.
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
    ):
        """
        Initialize the orchestrator with specialist agents.
        """
        self.planner = planner
        self.spec_agent = spec_agent
        self.exec_agent = exec_agent
        self.tracer = DecisionTracer()

        logger.info("AutonomousWorkflowOrchestrator initialized for A3 Specialist Mode")

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
        # PHASE 1: ARCHITECTURE (Planning) - Only once
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
                # Inject failure evidence from the previous trial if it exists
                if last_trial_feedback:
                    self.spec_agent.update_context(last_trial_feedback)

                # The Engineer produces the Blueprint (DetailedPlan)
                detailed_plan = await self.spec_agent.elaborate_plan(goal, plan)
                final_blueprint = detailed_plan  # Capture for construction phase
            except Exception as e:
                logger.error("❌ Engineering failed: %s", e)
                last_trial_feedback = f"Engineering Error: {e!s}"
                # Backtrack to start of loop for retry
                continue

            # PHASE 2.5: PACKAGING (Staging)
            # We convert the blueprint into a filesystem transaction (The Crate)
            crate_id = await self._stage_in_crate(goal, final_blueprint)
            if not crate_id:
                last_trial_feedback = (
                    "Infrastructure Error: Crate creation failed (Check model/params)."
                )
                continue

            # PHASE 3: THE TRIAL (Canary Validation)
            # We run the Audit on the Crate in the sandbox
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
                break  # Exit loop, the blueprint is proven safe!
            else:
                logger.warning("❌ CANARY TRIAL FAILED.")
                last_trial_feedback = f"TRIAL EVIDENCE: Your previous code failed the audit. Findings: {trial_report}"

                self.tracer.record(
                    agent="Orchestrator",
                    decision_type="retry_logic",
                    rationale="Canary trial detected constitutional violations.",
                    chosen_action="Backtrack to Engineering with Feedback",
                    context={"attempt": attempts, "violations": trial_report},
                    confidence=0.5,
                )

                if attempts == max_attempts:
                    return self._create_failed_workflow_result(
                        goal,
                        "engineering",
                        f"Failed after {max_attempts} attempts. Last evidence: {trial_report}",
                        time.time() - workflow_start_time,
                    )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PHASE 4: CONSTRUCTION (Execution) - Final Application
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # GUARD: Prevent crash if loop exited without a valid blueprint
        if final_blueprint is None:
            return self._create_failed_workflow_result(
                goal,
                "engineering",
                "Failed to generate a valid blueprint (Step params error).",
                time.time() - workflow_start_time,
            )

        logger.info("")
        logger.info("🏗️ PHASE 4: CONSTRUCTION (Execution)")
        logger.info("-" * 80)

        try:
            # The 'Contractor' applies the 'Proven Blueprint' to the production 'Body'
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
                    "canary_validated": True,
                    "final_status": "applied_after_trial",
                },
            )

        except Exception as e:
            logger.error("❌ Final execution crashed: %s", e)
            return self._create_failed_workflow_result(
                goal, "execution", str(e), time.time() - workflow_start_time
            )

    async def _stage_in_crate(self, goal: str, detailed_plan: Any) -> str | None:
        """Calls the Body action to stage the code in an Intent Crate."""
        logger.info("📦 Staging blueprint in Intent Crate...")

        # Collect generated code from the plan
        files = {
            step.params["file_path"]: step.params["code"]
            for step in detailed_plan.steps
            if "code" in step.params and step.params.get("file_path")
        }

        if not files:
            # If no files need to be written, we don't need a crate
            return "no_crate_required"

        # Route through the Body's ActionExecutor (Governmental Gateway)
        result = await self.exec_agent.executor.execute(
            action_id="crate.create", write=True, intent=goal, payload_files=files
        )

        return result.data.get("crate_id") if result.ok else None

    async def _run_canary_trial(self, crate_id: str) -> tuple[bool, str]:
        """Invokes the CrateProcessingService (The Judge) to audit the crate."""
        if crate_id == "no_crate_required":
            return True, "Passed (No code changes)"

        logger.info("🧪 Sandbox: Proving Crate '%s' safe...", crate_id)

        try:
            from body.services.crate_processing_service import CrateProcessingService

            processor = CrateProcessingService()

            # The Trial: Copy repo, apply crate, run audit
            success, findings = await processor.validate_crate_by_id(crate_id)

            if success:
                return True, "Passed"

            # Format failure messages for the next Engineering attempt
            return False, " | ".join([f"[{f.check_id}] {f.message}" for f in findings])

        except Exception as e:
            return False, f"Trial Infrastructure Error: {e!s}"

    def _create_failed_workflow_result(
        self, goal: str, phase: str, error: str, duration: float
    ) -> WorkflowResult:
        """Helper to create a compliant failure result."""
        from shared.models.workflow_models import DetailedPlan

        # Constitutional Rule: DetailedPlan requires 'failed_at' in metadata if steps are empty
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

    # ID: 33681fc1-7f72-44e0-a77d-83a89d7f5ea0
    async def save_decision_trace(self) -> None:
        await self.tracer.save_trace()
