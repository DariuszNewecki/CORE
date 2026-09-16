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
from shared.models.workflow_models import PhaseResult
from will.agents.planner_agent import PlannerAgent


if TYPE_CHECKING:
    from shared.context import CoreContext
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)


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
            result = await self._recon.execute(repo_path=self._repo_path)
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
