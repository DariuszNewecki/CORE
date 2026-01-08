# src/features/self_healing/clarity_service_v2.py

"""
Adaptive Clarity Orchestrator (V2.2).
Implements Recursive Self-Correction with Tiered Reasoning Escalation
AND Network Exception Resilience.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from body.analyzers.file_analyzer import FileAnalyzer
from body.evaluators.clarity_evaluator import ClarityEvaluator
from shared.config import settings
from shared.logger import getLogger
from shared.utils.parsing import extract_python_code_from_response
from will.strategists.clarity_strategist import ClarityStrategist


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: 1e2f3a4b-5c6d-7e8f-9a0b-1c2d3e4f5a6b
async def remediate_clarity_v2(
    context: CoreContext, file_path: Path, write: bool = False
):
    """
    V2.2 Orchestrator: Robust Loop (Analyze -> Strategize -> [Refactor -> Fix] x3 -> Apply).
    Handles Network/API failures without crashing the entire workflow.
    """
    # 1. PATH NORMALIZATION (Preserved from V2.1)
    abs_file_path = file_path.resolve()
    repo_root = settings.REPO_PATH.resolve()

    try:
        rel_path_str = str(abs_file_path.relative_to(repo_root))
    except ValueError:
        rel_path_str = str(file_path).replace("\\", "/")

    logger.info("🧪 Starting V2 Adaptive Clarity Refactoring: %s", rel_path_str)

    # 2. ANALYZE (Preserved from V2.1)
    analyzer = FileAnalyzer(context)
    analysis = await analyzer.execute(file_path=rel_path_str)

    if not analysis.ok:
        logger.error("❌ Analysis failed: %s", analysis.data.get("error"))
        return

    # 3. STRATEGIZE (Preserved from V2.1)
    line_count = analysis.metadata.get("line_count", 0)
    complexity_score = analysis.metadata.get("total_definitions", 0)

    strategist = ClarityStrategist()
    strategy = await strategist.execute(
        complexity_score=complexity_score, line_count=line_count
    )

    logger.info("🎯 Selected Strategy: %s", strategy.data["strategy"])

    original_code = abs_file_path.read_text(encoding="utf-8")
    current_prompt = (
        f"You are a Senior Architect. Task: Refactor the following code for {strategy.data['strategy']}.\n"
        f"Specific Instruction: {strategy.data['instruction']}\n\n"
        f"SOURCE CODE:\n{original_code}\n\n"
        "Return ONLY the updated Python code. Do not include markdown fences."
    )

    # 4. THE ADAPTIVE LOOP WITH RESILIENCE (Enhanced from V2.1)
    max_attempts = 3
    attempt = 0
    final_code = None

    while attempt < max_attempts:
        attempt += 1

        # TIERED ESCALATION (Preserved from V2.1)
        use_expert = attempt == max_attempts
        tier_label = "EXPERT (High-Reasoning)" if use_expert else "STANDARD (Economy)"
        logger.info(
            "🔄 Attempt %d/%d using %s reasoning tier...",
            attempt,
            max_attempts,
            tier_label,
        )

        try:
            # WILL LAYER: AI Request
            coder = await context.cognitive_service.aget_client_for_role(
                "Coder", high_reasoning=use_expert
            )
            response_raw = await coder.make_request_async(
                current_prompt, user_id="clarity_v2"
            )

            new_code = extract_python_code_from_response(response_raw) or response_raw

            # BODY LAYER: Evaluation
            evaluator = ClarityEvaluator()
            verdict = await evaluator.execute(
                original_code=original_code, new_code=new_code
            )

            if verdict.ok:
                if verdict.data.get("is_better", False):
                    # SUCCESS BRANCH
                    reduction = verdict.data.get("improvement_ratio", 0) * 100
                    logger.info(
                        "✅ Refactor successful! Complexity Reduction: %.1f%%",
                        reduction,
                    )
                    final_code = new_code
                    break
                else:
                    # COMPLEXITY INCREASE BRANCH (Feedback loop preserved)
                    logger.warning(
                        "⚠️ Refactor resulted in higher complexity (%s).",
                        verdict.data.get("new_cc"),
                    )
                    current_prompt = (
                        f"Your previous attempt actually increased code complexity (New CC: {verdict.data.get('new_cc')} vs Orig CC: {verdict.data.get('original_cc')}). "
                        f"Try again, but focus on RADICAL SIMPLIFICATION of the logic:\n\n{original_code}"
                    )
            else:
                # SYNTAX ERROR BRANCH (Feedback loop preserved)
                error_msg = verdict.data.get("error", "Syntax Error")
                logger.warning("❌ Syntax Error detected in AI output: %s", error_msg)
                current_prompt = (
                    f"Your previous refactoring has a SYNTAX ERROR:\n{error_msg}\n\n"
                    "Please fix the syntax and provide the full code again. SOURCE:\n"
                    f"{original_code}"
                )

        except Exception as e:
            # NETWORK/API RESILIENCE (New in V2.2)
            logger.error(
                "🚨 API/Network Error on attempt %d: %s", attempt, type(e).__name__
            )
            if attempt < max_attempts:
                logger.info("   -> Connection interrupted. Retrying next tier...")
                # We continue the loop without changing current_prompt (to retry the same task)
                continue
            else:
                logger.error(
                    "❌ All attempts failed due to persistent network/API issues."
                )

    # 5. FINAL ACTION (Preserved from V2.1)
    if final_code:
        if write:
            from body.atomic.executor import ActionExecutor

            executor = ActionExecutor(context)
            await executor.execute(
                "file.edit", write=True, file_path=rel_path_str, code=final_code
            )
        else:
            logger.info(
                "💡 [DRY RUN] Validated refactor ready. Complexity reduction confirmed."
            )
    else:
        logger.error(
            "❌ Failed to generate a valid/better refactor after %d attempts.",
            max_attempts,
        )
