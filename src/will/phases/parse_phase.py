# src/will/phases/parse_phase.py

"""
Parse Phase - Constitutional composite that drives PlannerAgent.

Converts interpreted intent (WorkflowContext.goal) into a structured
execution plan by invoking PlannerAgent directly.  Results are stored
under BOTH the canonical 'parse' key AND the legacy 'planning' key so
that CodeGenerationPhase (which reads 'planning') continues to work
without modification.

ARCHITECTURAL NOTE:
  PlanningPhase (src/will/phases/planning_phase.py) is a generic utility
  class with no constitutional-phase interface.  It has no execute() method
  and must NOT be used here.  The correct agent for constitutional planning
  is PlannerAgent (src/will/agents/planner_agent.py).
"""

from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from body.analyzers.target_reconnaissance_analyzer import (
    TargetReconnaissanceAnalyzer,
)
from shared.logger import getLogger
from shared.models.target_binding import evaluation_view
from shared.models.workflow_models import PhaseResult
from will.agents.investigation_planner import (
    InvestigationPlanError,
    create_investigation_plan,
    investigation_decisions,
)
from will.agents.planner_agent import PlannerAgent


if TYPE_CHECKING:
    from shared.context import CoreContext
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)

# The one workflow for which reconnaissance is mandatory rather than helpful.
EVALUATION_WORKFLOW = "evaluation"


# ID: 15c02b6a-ab2d-4026-ac2b-ab7a385f8c90
class ParsePhase:
    """
    Constitutional Parse phase.

    Converts interpreted intent into a structured operational plan by
    driving PlannerAgent.  Mirrors results under the legacy 'planning'
    key for backward compatibility with CodeGenerationPhase.
    """

    def __init__(self, core_context: CoreContext):
        self.context = core_context

        # Resolve repo_path from git_service (always present after bootstrap).
        repo_path: Path = Path(core_context.git_service.repo_path)

        # Wire PlannerAgent from CoreContext services.
        # qdrant_service is optional — PlannerAgent degrades gracefully if absent.
        if core_context.cognitive_service is None:
            raise ValueError("cognitive_service required for ParsePhase")
        self._planner = PlannerAgent(
            cognitive_service=core_context.cognitive_service,
            repo_path=repo_path,
            qdrant_service=getattr(core_context, "qdrant_service", None),
        )
        self._repo_path = repo_path
        # Reconnaissance reads the subject-only view (ruling M2): the original
        # snapshot when externally bound, never the execution copy with its
        # installed apparatus.
        self._recon_root, self._recon_scope = evaluation_view(core_context)
        self._recon = TargetReconnaissanceAnalyzer()

    # ID: 794bcd6c-de50-4ac2-868c-d6de52b277b9
    async def execute(self, context: WorkflowContext) -> PhaseResult:
        """
        Execute the parse phase: goal → execution plan via PlannerAgent.

        Stores the plan under both 'parse' and 'planning' in context.results
        so downstream phases that read either key continue to work.
        """
        start = time.time()

        goal: str = context.goal

        logger.info("🗂️  PARSE Phase: Planning goal: '%s'", goal)

        # Ground the plan in what the target actually contains. Without this the
        # planner reasons from CORE's own shape, which is wrong for any bound
        # external target (#895 U1).
        recon_text, recon_data = await self._reconnoitre()

        if context.workflow_type == EVALUATION_WORKFLOW:
            return await self._plan_investigation(
                context, goal, recon_text, recon_data, start
            )

        try:
            # PlannerAgent.create_execution_plan handles constitutional RAG,
            # action-registry introspection, and plan validation internally.
            plan = await self._planner.create_execution_plan(goal, recon_text)
        except Exception as exc:
            logger.error("❌ PARSE: PlannerAgent failed: %s", exc, exc_info=True)
            return PhaseResult(
                name="parse",
                ok=False,
                error=f"Planning failed: {exc}",
                duration_sec=time.time() - start,
            )

        if not plan:
            logger.error("❌ PARSE: PlannerAgent returned an empty plan.")
            return PhaseResult(
                name="parse",
                ok=False,
                error="PlannerAgent produced no executable steps for this goal.",
                duration_sec=time.time() - start,
            )

        logger.info("✅ PARSE: Plan ready — %d steps", len(plan))
        for i, step in enumerate(plan, 1):
            logger.debug("   Step %d: [%s] %s", i, step.action, step.step)

        plan_data = {
            "execution_plan": plan,  # list[ExecutionTask] — consumed by CodeGenerationPhase
            "steps_count": len(plan),
            "goal": goal,
            "reconnaissance": recon_data,
            "decisions": self._decision_records(),
        }

        # Mirror under both keys.
        context.results["parse"] = plan_data
        context.results["planning"] = plan_data

        return PhaseResult(
            name="parse",
            ok=True,
            data=plan_data,
            duration_sec=time.time() - start,
        )

    async def _reconnoitre(self) -> tuple[str, dict[str, Any]]:
        """Describe the bound target for the planner.

        A failed reconnaissance degrades planning rather than stopping it: the
        planner can still work from the goal alone, so the absence is recorded
        and passed on as an absence instead of being raised. Returning an empty
        report here would claim the target is empty, which is a different and
        false statement.
        """
        try:
            result = await self._recon.execute(repo_path=self._recon_root)
        except Exception as exc:  # defensive: recon must never fail the phase
            logger.warning("PARSE: reconnaissance raised: %s", exc, exc_info=True)
            return "", {"available": False, "reason": str(exc)}

        if not result.ok:
            reason = getattr(result, "reason", "reconnaissance refused")
            logger.warning("PARSE: reconnaissance unavailable: %s", reason)
            return "", {"available": False, "reason": reason}

        logger.info(
            "PARSE: reconnaissance ready — %d files, %d unavailable topics",
            result.data["recon_raw"]["file_count"],
            len(result.data["unavailable"]),
        )
        return result.data["recon_text"], {
            "available": True,
            "digest": result.data["recon_digest"],
            "raw": result.data["recon_raw"],
            "unavailable": result.data["unavailable"],
            "view": self._recon_scope,
        }

    def _decision_records(self) -> list[dict[str, Any]]:
        """Mirror the planner's decision trace for the run's own record.

        The tracer keeps its decisions in memory and PlannerAgent never calls
        save_trace(), so nothing durable exists to read back later. Copying the
        structured decisions here is what puts the planner's reasoning on the
        run's identity -- rationale, alternatives considered and confidence, not
        chain-of-thought.
        """
        tracer = getattr(self._planner, "tracer", None)
        decisions = getattr(tracer, "decisions", None)
        if not decisions:
            return []

        records: list[dict[str, Any]] = []
        for decision in decisions:
            try:
                records.append(asdict(decision))
            except TypeError:  # not a dataclass — record what can be read
                records.append({"decision": str(decision)})
        return records

    async def _plan_investigation(
        self,
        context: WorkflowContext,
        goal: str,
        recon_text: str,
        recon_data: dict[str, Any],
        start: float,
    ) -> PhaseResult:
        """Plan a read-only investigation, refusing outright without reconnaissance.

        The evaluation workflow does not share the goal-only degradation path the
        mutation workflows have. A failed reconnaissance here is reported as
        UNAVAILABLE and the phase stops: findings about a target that was never
        examined are indistinguishable from findings about one that was, and for
        a scored trial that is worse than no run at all.
        """
        if not recon_data.get("available"):
            reason = recon_data.get("reason", "reconnaissance did not run")
            logger.error("PARSE: evaluation refused — reconnaissance unavailable")
            return PhaseResult(
                name="parse",
                ok=False,
                error=(
                    f"UNAVAILABLE: evaluation requires reconnaissance and it was "
                    f"not available ({reason}). Planning blind is refused."
                ),
                data={"reconnaissance": recon_data},
                duration_sec=time.time() - start,
            )

        try:
            plan = await create_investigation_plan(
                cognitive_service=self.context.cognitive_service,
                goal=goal,
                reconnaissance_report=recon_text,
            )
        except InvestigationPlanError as exc:
            logger.error("PARSE: investigation planning refused: %s", exc)
            return PhaseResult(
                name="parse",
                ok=False,
                error=str(exc),
                data={"reconnaissance": recon_data},
                duration_sec=time.time() - start,
            )

        plan_data: dict[str, Any] = {
            "investigation_plan": plan,
            "steps_count": len(plan),
            "goal": goal,
            "reconnaissance": recon_data,
            # This planner has no DecisionTracer; its reasoning is the plan's
            # own stated purpose per step (2026-09-17 cold-run finding).
            "decisions": investigation_decisions(plan),
        }
        context.results["parse"] = plan_data
        context.results["planning"] = plan_data

        logger.info("PARSE: investigation plan ready — %d read-only steps", len(plan))
        return PhaseResult(
            name="parse",
            ok=True,
            data=plan_data,
            duration_sec=time.time() - start,
        )
