# src/will/self_healing/complexity_service.py
"""
Complexity Remediation Service — V2.4 Adaptive Orchestrator.

Constitutional promotions in this version (V2.4):
- Logic Conservation: _check_for_lobotomy() replaced with the constitutional
  LogicConservationValidator (body/validators/logic_conservation_validator.py).
  The gate is no longer a private method — it is a proper Body component whose
  ComponentResult is passed to GovernanceDecider as part of the evaluation chain.
  This means every refactor workflow routes through the same constitutional gate,
  not just ComplexityRemediationService.

- Layer Separation: Will layer orchestration only. Delegates to ExecutionAgent.
- Blueprinting:     Produces a DetailedPlan instead of manual loop execution.
- Shadow Truth:     Integrated with LimbWorkspace.

LAYER: will/self_healing — orchestration only. No file writes. No DB access.
All execution delegated to Body via ExecutionAgent and ActionExecutor.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from body.analyzers.file_analyzer import FileAnalyzer
from body.evaluators.clarity_evaluator import ClarityEvaluator
from body.validators.logic_conservation_validator import LogicConservationValidator
from shared.ai.prompt_model import PromptModel
from shared.infrastructure.context.limb_workspace import LimbWorkspace
from shared.logger import getLogger
from shared.models.workflow_models import DetailedPlan, DetailedPlanStep
from shared.utils.parsing import extract_python_code_from_response, parse_write_blocks
from will.agents.execution_agent import ExecutionAgent
from will.orchestration.decision_tracer import DecisionTracer
from will.strategists.complexity_strategist import ComplexityStrategist


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: b1c2d3e4-f5a6-7890-abcd-ef1234567890
class ComplexityRemediationService:
    """
    Orchestrates the reduction of Cyclomatic Complexity via structural
    decomposition.

    V2.4 change: the logic conservation check is now a constitutional
    Body component (LogicConservationValidator) whose result feeds the
    GovernanceDecider. The private _check_for_lobotomy method is removed.
    """

    def __init__(self, context: CoreContext) -> None:
        self.context = context
        self.tracer = DecisionTracer(
            path_resolver=context.path_resolver, agent_name="ComplexityHealer"
        )

    # ID: d4e5f6a7-b8c9-0123-defa-567890abcdef
    async def remediate(self, file_path: Path, write: bool = False) -> bool:
        """
        Executes the 7-Phase Complexity Remediation Workflow.
        """
        start_time = time.perf_counter()
        rel_path = str(file_path.relative_to(self.context.git_service.repo_path))

        logger.info("⚙️  [V2.4] Initiating Complexity Remediation: %s", rel_path)

        # ── 1. ANALYZE (Sensation) ────────────────────────────────────────────
        analyzer = FileAnalyzer(self.context)
        analysis = await analyzer.execute(file_path=rel_path)
        if not analysis.ok:
            logger.error("❌ Analysis failed: %s", analysis.data.get("error"))
            return False

        # ── 2. STRATEGIZE (Decision) ──────────────────────────────────────────
        total_defs = analysis.metadata.get("total_definitions", 0)
        strategist = ComplexityStrategist()
        strategy_res = await strategist.execute(complexity_score=total_defs)
        strategy = strategy_res.data

        # ── 3. GENERATE & EVALUATE (Reflex Loop) ─────────────────────────────
        workspace = LimbWorkspace(self.context.git_service.repo_path)
        original_code = (self.context.git_service.repo_path / rel_path).read_text(
            encoding="utf-8"
        )

        final_code_map = await self._run_reflex_loop(
            rel_path, original_code, strategy, workspace
        )

        if not final_code_map:
            logger.error("❌ Failed to generate a mathematically improved refactor.")
            return False

        # ── 4. DECIDE (Blueprinting) ──────────────────────────────────────────
        blueprint = self._build_execution_blueprint(
            rel_path, final_code_map, context="Complexity reduction"
        )

        # ── 5. EXECUTE (Will delegates to Agent) ─────────────────────────────
        agent = ExecutionAgent(executor=self.context.action_executor, write=write)
        exec_results = await agent.execute_plan(blueprint)

        duration = time.perf_counter() - start_time
        if exec_results.success:
            logger.info("✅ Complexity remediation successful (%.2fs)", duration)
            return True

        return False

    # ID: e5f6a7b8-c9d0-1e2f-3a4b-5c6d7e8f9012
    async def _run_reflex_loop(
        self,
        rel_path: str,
        original_code: str,
        strategy: dict,
        workspace: LimbWorkspace,
        deletions_authorized: bool = False,
    ) -> dict[str, str] | None:
        """
        The 'Hand' Reflex: iteratively improves code until it passes both
        the Clarity gate and the Logic Conservation gate.

        Gate order (both must pass):
            1. ClarityEvaluator   — mathematical improvement (complexity reduction)
            2. LogicConservationValidator — mass conservation (anti-lobotomy)

        If either gate fires, the pain signal feeds back into the next attempt.
        After 3 failed attempts the loop yields None.

        Args:
            rel_path:             Relative path of the file being refactored.
            original_code:        Source before any modification.
            strategy:             Strategist decision dict with 'instruction' key.
            workspace:            Shadow workspace for safe iteration.
            deletions_authorized: Pass-through flag for large intentional removals.
                                  False by default — complexity refactors must
                                  conserve logic mass.
        """
        model = PromptModel.load("complexity_reflex_refactor")
        current_prompt = (
            f"Refactor {rel_path} to reduce complexity. "
            f"Strategy: {strategy['instruction']}\n\nCODE:\n{original_code}"
        )
        conservation_validator = LogicConservationValidator()

        for attempt in range(3):
            logger.info("🔁 Reflex Attempt %d/3...", attempt + 1)

            # ── GENERATE ──────────────────────────────────────────────────────
            coder = await self.context.cognitive_service.aget_client_for_role("Coder")
            response = await model.invoke(
                context={"current_prompt": current_prompt},
                client=coder,
                user_id="complexity_reflex",
            )

            blocks = parse_write_blocks(response)
            proposed_map: dict[str, str] = (
                blocks
                if blocks
                else {
                    rel_path: (extract_python_code_from_response(response) or response)
                }
            )
            primary_new_code = proposed_map.get(rel_path) or next(
                iter(proposed_map.values())
            )

            # ── EVALUATE 1: Clarity (mathematical improvement) ─────────────
            clarity_evaluator = ClarityEvaluator()
            clarity_verdict = await clarity_evaluator.evaluate(
                original_code=original_code, new_code=primary_new_code
            )

            # ── EVALUATE 2: Logic Conservation (constitutional gate) ────────
            conservation_verdict = await conservation_validator.evaluate(
                original_code=original_code,
                proposed_map=proposed_map,
                deletions_authorized=deletions_authorized,
            )

            # ── DECIDE: pass both or feed pain signal ──────────────────────
            clarity_ok = clarity_verdict.ok and clarity_verdict.data.get("is_better")
            conservation_ok = conservation_verdict.ok

            if clarity_ok and conservation_ok:
                logger.info(
                    "✅ Reflex attempt %d passed both gates (ratio=%.2f).",
                    attempt + 1,
                    conservation_verdict.data.get("ratio", 1.0),
                )
                return proposed_map

            # Build pain signal from whichever gate(s) fired.
            pain_parts: list[str] = []
            if not clarity_ok:
                pain_parts.append("code is still too complex")
            if not conservation_ok:
                pain_parts.append(
                    f"logic evaporation detected — "
                    f"proposed code is only "
                    f"{conservation_verdict.data.get('ratio', 0) * 100:.1f}% "
                    f"of original size. Preserve ALL domain logic while splitting."
                )

            pain_signal = "; ".join(pain_parts)
            logger.warning("⚠️  Reflex attempt %d failed: %s", attempt + 1, pain_signal)
            current_prompt += (
                f"\n\n⚠️ PAIN SIGNAL (attempt {attempt + 1}): {pain_signal}"
            )

        logger.error(
            "❌ All 3 reflex attempts failed for %s. "
            "Both ClarityEvaluator and LogicConservationValidator must pass.",
            rel_path,
        )
        return None

    # ID: f6a7b8c9-d0e1-2f3a-4b5c-6d7e8f901234
    def _build_execution_blueprint(
        self,
        original_path: str,
        code_map: dict[str, str],
        context: str,
    ) -> DetailedPlan:
        """
        Converts the reasoning result into a formal Construction Plan.

        Rule: if splitting (creating new files), the monolith must be pruned
        first to avoid duplicate symbols in the codebase.
        """
        steps: list[DetailedPlanStep] = []

        if len(code_map) > 1 or original_path not in code_map:
            steps.append(
                DetailedPlanStep(
                    action="file.delete",
                    description=f"Pruning monolithic file: {original_path}",
                    params={"file_path": original_path},
                )
            )

        for path, code in code_map.items():
            steps.append(
                DetailedPlanStep(
                    action="file.edit",
                    description=f"Creating/Updating cohesive unit: {path}",
                    params={"file_path": path, "code": code},
                )
            )

        return DetailedPlan(goal=context, steps=steps)
