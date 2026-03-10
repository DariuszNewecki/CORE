# src/will/self_healing/clarity_service.py

"""
Adaptive Clarity Orchestrator (V2.3) - ROADMAP COMPLIANT.
Follows: INTERPRET ? ANALYZE ? STRATEGIZE ? GENERATE ? EVALUATE ? DECIDE ? EXECUTE.

Preserves V2.2 Recursive Self-Correction, Tiered Reasoning, and Resilience.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from body.analyzers.file_analyzer import FileAnalyzer
from body.evaluators.clarity_evaluator import ClarityEvaluator
from shared.ai.prompt_model import PromptModel
from shared.infrastructure.config_service import ConfigService
from shared.logger import getLogger
from shared.utils.parsing import extract_python_code_from_response
from will.deciders.governance_decider import GovernanceDecider  # NEW
from will.interpreters.request_interpreter import CLIArgsInterpreter  # NEW
from will.strategists.clarity_strategist import ClarityStrategist


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: 1e2f3a4b-5c6d-7e8f-9a0b-1c2d3e4f5a6b
async def remediate_clarity_v2(
    context: CoreContext,
    file_path: Path,
    write: bool = False,
    config_service: ConfigService | None = None,
):
    """
    V2.3 Orchestrator: Combines high-resilience adaptive loops with
    formal constitutional gatekeeping.
    """

    # =========================================================================
    # 1. PHASE: INTERPRET
    # =========================================================================
    interpreter = CLIArgsInterpreter()
    task_result = await interpreter.execute(
        command="fix", subcommand="clarity", targets=[str(file_path)], write=write
    )
    task = task_result.data["task"]
    # Ensure we use normalized path from interpreter
    rel_path_str = task.targets[0] if task.targets else str(file_path)

    logger.info("? [V2.3] Starting Adaptive Clarity Workflow: %s", rel_path_str)

    # =========================================================================
    # 2. PHASE: ANALYZE
    # =========================================================================
    analyzer = FileAnalyzer(context)
    analysis = await analyzer.execute(file_path=rel_path_str)

    if not analysis.ok:
        logger.error("? Analysis failed: %s", analysis.data.get("error"))
        return

    # =========================================================================
    # 3. PHASE: STRATEGIZE
    # =========================================================================
    line_count = analysis.metadata.get("line_count", 0)
    complexity_score = analysis.metadata.get("total_definitions", 0)

    strategist = ClarityStrategist()
    strategy = await strategist.execute(
        complexity_score=complexity_score, line_count=line_count
    )

    logger.info("? Selected Strategy: %s", strategy.data["strategy"])

    # =========================================================================
    # 4 & 5. THE ADAPTIVE LOOP (GENERATE + EVALUATE)
    # =========================================================================
    if config_service is not None:
        repo_root = Path(await config_service.get("REPO_PATH", required=True))
    else:
        async with context.registry.session() as session:
            runtime_config = await ConfigService.create(session)
            repo_root = Path(await runtime_config.get("REPO_PATH", required=True))

    original_code = (repo_root / rel_path_str).read_text(encoding="utf-8")

    model = PromptModel.load("clarity_v2_refactor")

    max_attempts = 3
    attempt = 0
    final_code = None
    last_verdict = None

    while attempt < max_attempts:
        attempt += 1

        use_expert = attempt == max_attempts
        tier_label = "EXPERT (High-Reasoning)" if use_expert else "STANDARD (Economy)"
        logger.info(
            "? Attempt %d/%d using %s tier...", attempt, max_attempts, tier_label
        )

        try:
            # 4. PHASE: GENERATE (Will Layer)
            coder = await context.cognitive_service.aget_client_for_role(
                "Coder", high_reasoning=use_expert
            )

            context_dict = {
                "strategy": strategy.data["strategy"],
                "instruction": strategy.data["instruction"],
                "original_code": original_code,
            }

            if attempt > 1 and last_verdict:
                if last_verdict.ok and not last_verdict.data.get("is_better", False):
                    context_dict["feedback_type"] = "complexity_increased"
                    context_dict["new_cc"] = last_verdict.data.get("new_cc")
                    context_dict["original_cc"] = last_verdict.data.get("original_cc")
                elif not last_verdict.ok:
                    context_dict["feedback_type"] = "syntax_error"
                    context_dict["error_msg"] = last_verdict.data.get(
                        "error", "Syntax Error"
                    )

            response_raw = await model.invoke(
                context=context_dict, client=coder, user_id="clarity_v2"
            )
            new_code = extract_python_code_from_response(response_raw) or response_raw

            # 5. PHASE: EVALUATE (Body Layer)
            evaluator = ClarityEvaluator()
            last_verdict = await evaluator.execute(
                original_code=original_code, new_code=new_code
            )

            if last_verdict.ok:
                if last_verdict.data.get("is_better", False):
                    # SUCCESS: Code is valid and mathematically improved
                    reduction = last_verdict.data.get("improvement_ratio", 0) * 100
                    logger.info(
                        "? Refactor successful! Complexity Reduction: %.1f%%",
                        reduction,
                    )
                    final_code = new_code
                    break
                else:
                    # FEEDBACK: Complexity increased
                    logger.warning(
                        "?? Refactor resulted in higher complexity (%s).",
                        last_verdict.data.get("new_cc"),
                    )
            else:
                # FEEDBACK: Syntax Error
                error_msg = last_verdict.data.get("error", "Syntax Error")
                logger.warning("? Syntax Error detected in AI output: %s", error_msg)

        except Exception as e:
            # RESILIENCE: Network/API Error
            logger.error(
                "? API/Network Error on attempt %d: %s", attempt, type(e).__name__
            )
            if attempt >= max_attempts:
                logger.error("? All attempts failed due to persistent network issues.")

    # =========================================================================
    # 6. PHASE: DECIDE (Authorization Gate)
    # =========================================================================
    decider = GovernanceDecider()
    # We pass the last evaluation results to the decider.
    # If the loop finished without break, last_verdict will reflect why.
    authorization = await decider.execute(
        evaluation_results=[last_verdict] if last_verdict else [],
        risk_tier="ELEVATED" if write else "ROUTINE",
    )

    # =========================================================================
    # 7. PHASE: EXECUTION (Final Application)
    # =========================================================================
    if authorization.data["can_proceed"] and final_code:
        if write:
            from body.atomic.executor import ActionExecutor

            executor = ActionExecutor(context)
            logger.info(
                "??  Authorization Granted. Applying refactor via ActionExecutor..."
            )

            await executor.execute(
                "file.edit", write=True, file_path=rel_path_str, code=final_code
            )
        else:
            logger.info(
                "? [DRY RUN] Validated refactor ready. Complexity reduction confirmed."
            )
    else:
        # Explain why we stopped
        blockers = authorization.data.get("blockers", ["No valid refactor produced"])
        logger.error("? EXECUTION HALTED: %s", ", ".join(blockers))
