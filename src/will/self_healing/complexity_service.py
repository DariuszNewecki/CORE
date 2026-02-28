# src/will/self_healing/complexity_service.py
# ID: f1d2e3b4-a5b6-7890-c1d2-e3f4a5b6c7d8

"""
Complexity Remediation Service - V2.3 Adaptive Orchestrator.

CONSTITUTIONAL PROMOTION:
- Layer Separation: Will layer orchestration only. Delegates to ExecutionAgent.
- Logic Conservation: Enforces the 'Anti-Lobotomy' gate.
- Blueprinting: Produces a DetailedPlan instead of manual loop execution.
- Shadow Truth: Integrated with LimbWorkspace.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from body.analyzers.file_analyzer import FileAnalyzer
from body.evaluators.clarity_evaluator import ClarityEvaluator
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
    Orchestrates the reduction of Cyclomatic Complexity via structural decomposition.
    """

    def __init__(self, context: CoreContext):
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

        logger.info("🧪 [V2.3] Initiating Complexity Remediation: %s", rel_path)

        # 1. ANALYZE (Sensation)
        analyzer = FileAnalyzer(self.context)
        analysis = await analyzer.execute(file_path=rel_path)
        if not analysis.ok:
            logger.error("❌ Analysis failed: %s", analysis.data.get("error"))
            return False

        # 2. STRATEGIZE (Decision)
        total_defs = analysis.metadata.get("total_definitions", 0)
        strategist = ComplexityStrategist()
        strategy_res = await strategist.execute(complexity_score=total_defs)
        strategy = strategy_res.data

        # 3. GENERATE & EVALUATE (Reflex Loop)
        # Create a Shadow Workspace to "taste" the split logic
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

        # 4. DECIDE (Blueprinting)
        # Instead of calling ActionExecutor, we build a "Construction Blueprint"
        blueprint = self._build_execution_blueprint(
            rel_path, final_code_map, context="Complexity reduction"
        )

        # 5. EXECUTE (Will delegates to Agent)
        # Layer Separation: Will uses ExecutionAgent to talk to the Body
        agent = ExecutionAgent(executor=self.context.action_executor, write=write)
        exec_results = await agent.execute_plan(blueprint)

        duration = time.perf_counter() - start_time
        if exec_results.success:
            logger.info("✅ Complexity remediation successful (%.2fs)", duration)
            return True

        return False

    async def _run_reflex_loop(
        self,
        rel_path: str,
        original_code: str,
        strategy: dict,
        workspace: LimbWorkspace,
    ) -> dict[str, str] | None:
        """
        The 'Hand' Reflex: Iteratively improves code until it passes the gates.
        """
        current_prompt = f"Refactor {rel_path} to reduce complexity. Strategy: {strategy['instruction']}\n\nCODE:\n{original_code}"

        for attempt in range(3):
            logger.info("🔄 Reflex Attempt %d/3...", attempt + 1)

            # GENERATE
            coder = await self.context.cognitive_service.aget_client_for_role("Coder")
            response = await coder.make_request_async(
                current_prompt, user_id="complexity_reflex"
            )

            # Sensation (Parsing write blocks or simple fenced code)
            blocks = parse_write_blocks(response)
            proposed_map = (
                blocks
                if blocks
                else {
                    rel_path: (extract_python_code_from_response(response) or response)
                }
            )

            # EVALUATE 1: Clarity (Mathematical improvement)
            evaluator = ClarityEvaluator()
            primary_new_code = proposed_map.get(rel_path) or next(
                iter(proposed_map.values())
            )

            # CHANGE: .execute() -> .evaluate()
            verdict = await evaluator.evaluate(
                original_code=original_code, new_code=primary_new_code
            )

            # EVALUATE 2: Logic Conservation (Anti-Lobotomy Gate)
            is_lobotomized = self._check_for_lobotomy(original_code, proposed_map)

            if verdict.ok and verdict.data.get("is_better") and not is_lobotomized:
                return proposed_map

            # Feedback Loop
            pain_signal = (
                "Code is still too complex"
                if not verdict.data.get("is_better")
                else "Lobotomy detected (too much code deleted)"
            )
            current_prompt += f"\n\n🚨 PAIN SIGNAL: {pain_signal}. Preserve all domain logic while splitting structures."

        return None

    def _check_for_lobotomy(
        self, original_code: str, proposed_map: dict[str, str]
    ) -> bool:
        """
        Constitutional Gate: Prevents the AI from deleting 50%+ of the code.
        """
        orig_len = len(original_code)
        new_total_len = sum(len(c) for c in proposed_map.values())

        if new_total_len < (orig_len * 0.5):
            logger.warning(
                "🚨 Logic Conservation Alert: Proposed code is only %.1f%% of original size.",
                (new_total_len / orig_len) * 100,
            )
            return True
        return False

    def _build_execution_blueprint(
        self, original_path: str, code_map: dict[str, str], context: str
    ) -> DetailedPlan:
        """
        Converts the reasoning result into a formal Construction Plan.
        """
        steps = []

        # Rule: If we are splitting (creating new files), we must prune the monolith
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
