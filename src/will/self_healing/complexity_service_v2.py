# src/features/self_healing/complexity_service_v2.py

"""
Adaptive Complexity Orchestrator (V2.3) - ROADMAP COMPLIANT.
Follows: INTERPRET → ANALYZE → STRATEGIZE → GENERATE → EVALUATE → DECIDE → EXECUTE.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from body.analyzers.file_analyzer import FileAnalyzer
from body.evaluators.clarity_evaluator import ClarityEvaluator
from shared.config import settings
from shared.logger import getLogger
from shared.utils.parsing import extract_python_code_from_response
from will.deciders.governance_decider import GovernanceDecider
from will.interpreters.request_interpreter import CLIArgsInterpreter
from will.strategists.complexity_strategist import ComplexityStrategist


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: 31bb8dba-f4d2-426a-8783-d09614085258
async def remediate_complexity_v2(
    context: CoreContext, file_path: Path, write: bool = False
):
    """
    V2.3 Orchestrator: Targets high complexity using proven V2 architecture.
    """

    # 1. PHASE: INTERPRET
    interpreter = CLIArgsInterpreter()
    task_result = await interpreter.execute(
        command="fix", subcommand="complexity", targets=[str(file_path)], write=write
    )
    task = task_result.data["task"]
    rel_path_str = task.targets[0]

    logger.info("🧪 [V2.3] Starting Adaptive Complexity Workflow: %s", rel_path_str)

    # 2. PHASE: ANALYZE
    analyzer = FileAnalyzer(context)
    analysis = await analyzer.execute(file_path=rel_path_str)
    if not analysis.ok:
        logger.error("❌ Analysis failed: %s", analysis.data.get("error"))
        return

    # 3. PHASE: STRATEGIZE
    total_defs = analysis.metadata.get("total_definitions", 0)

    strategist = ComplexityStrategist()
    strategy_result = await strategist.execute(complexity_score=total_defs)
    strategy = strategy_result.data
    logger.info("🎯 Selected Strategy: %s", strategy["strategy"])

    # 4 & 5. THE ADAPTIVE LOOP (GENERATE + EVALUATE)
    original_code = (settings.REPO_PATH / rel_path_str).read_text(encoding="utf-8")
    current_prompt = (
        f"You are a Principal Software Engineer. Task: Reduce Cyclomatic Complexity via {strategy['strategy']}.\n"
        f"Instruction: {strategy['instruction']}\n\n"
        f"SOURCE CODE:\n{original_code}\n"
    )

    max_attempts = 3
    attempt = 0
    final_code = None
    last_verdict = None

    while attempt < max_attempts:
        attempt += 1
        use_expert = attempt == max_attempts
        logger.info(
            "🔄 Attempt %d/%d (Expert=%s)...", attempt, max_attempts, use_expert
        )

        try:
            # 4. PHASE: GENERATE
            coder = await context.cognitive_service.aget_client_for_role(
                "Coder", high_reasoning=use_expert
            )
            response_raw = await coder.make_request_async(
                current_prompt, user_id="complexity_v2"
            )
            new_code = extract_python_code_from_response(response_raw) or response_raw

            # 5. PHASE: EVALUATE
            evaluator = ClarityEvaluator()
            last_verdict = await evaluator.execute(
                original_code=original_code, new_code=new_code
            )

            if last_verdict.ok and last_verdict.data.get("is_better", False):
                logger.info("✅ Complexity reduced successfully!")
                final_code = new_code
                break
            else:
                reason = last_verdict.data.get("error", "No improvement measured")
                logger.warning("⚠️  Attempt %d failed: %s. Retrying...", attempt, reason)
                current_prompt += f"\n\nCRITICAL: Your previous attempt failed. Reason: {reason}. Focus on SPLITTING logic."

        except Exception as e:
            logger.error("🚨 API Error: %s", e)

    # 6. PHASE: DECIDE
    decider = GovernanceDecider()
    # We ensure the decider sees the last verdict even if it was a failure
    eval_results = [last_verdict] if last_verdict else []

    authorization = await decider.execute(
        evaluation_results=eval_results, risk_tier="ELEVATED" if write else "ROUTINE"
    )

    # 7. PHASE: EXECUTION
    if authorization.data["can_proceed"] and final_code:
        if write:
            from body.atomic.executor import ActionExecutor

            executor = ActionExecutor(context)
            await executor.execute(
                "file.edit", write=True, file_path=rel_path_str, code=final_code
            )
            logger.info("⚖️  Complexity fix APPLIED.")
        else:
            logger.info("💡 [DRY RUN] Complexity fix VALIDATED and ready.")
    else:
        # IMPROVED ERROR REPORTING
        if not final_code:
            logger.error(
                "❌ EXECUTION HALTED: All %d attempts failed to produce a mathematical improvement.",
                max_attempts,
            )
        else:
            logger.error(
                "❌ EXECUTION HALTED: %s",
                ", ".join(authorization.data.get("blockers", [])),
            )
