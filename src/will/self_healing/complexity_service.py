# src/will/self_healing/complexity_service.py
# ID: 31bb8dba-f4d2-426a-8783-d09614085258

"""
Unified Complexity Remediation Service (V2.3).
Orchestrates the reduction of Cyclomatic Complexity using the 7-Phase flow.

Supports both:
1. In-place simplification (Refactoring a single file).
2. Structural decomposition (Splitting one file into many via write-blocks).

CONSTITUTIONAL ALIGNMENT:
- Removed legacy 'features/' paths.
- Natively Async: Prevents event-loop hijacking.
- Governed Execution: All mutations route through ActionExecutor.
- Logic Conservation: Evaluator proves improvement before DECIDE phase.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from body.analyzers.file_analyzer import FileAnalyzer
from body.atomic.executor import ActionExecutor
from body.evaluators.clarity_evaluator import ClarityEvaluator
from shared.infrastructure.config_service import ConfigService
from shared.logger import getLogger
from shared.utils.parsing import extract_python_code_from_response, parse_write_blocks
from will.deciders.governance_decider import GovernanceDecider
from will.interpreters.request_interpreter import CLIArgsInterpreter
from will.orchestration.decision_tracer import DecisionTracer
from will.strategists.complexity_strategist import ComplexityStrategist


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: 0e545e4a-22e4-42cc-b1f6-9e900445627b
async def remediate_complexity(
    context: CoreContext,
    file_path: Path,
    write: bool = False,
    config_service: ConfigService | None = None,
) -> None:
    """
    Consolidated Orchestrator: Targets high complexity using the V2.3 Adaptive Loop.

    Replaces both 'complexity_service_v2.py' and the legacy 'complexity_service.py'.
    """
    tracer = DecisionTracer(
        path_resolver=context.path_resolver, agent_name="ComplexityHealer"
    )
    start_time = time.perf_counter()

    # =========================================================================
    # 1. PHASE: INTERPRET
    # =========================================================================
    interpreter = CLIArgsInterpreter()
    task_result = await interpreter.execute(
        command="fix", subcommand="complexity", targets=[str(file_path)], write=write
    )
    task = task_result.data["task"]
    rel_path_str = task.targets[0]

    logger.info("🧪 [V2.3] Starting Adaptive Complexity Workflow: %s", rel_path_str)

    # =========================================================================
    # 2. PHASE: ANALYZE
    # =========================================================================
    analyzer = FileAnalyzer(context)
    analysis = await analyzer.execute(file_path=rel_path_str)
    if not analysis.ok:
        logger.error("❌ Analysis failed: %s", analysis.data.get("error"))
        return

    # =========================================================================
    # 3. PHASE: STRATEGIZE
    # =========================================================================
    total_defs = analysis.metadata.get("total_definitions", 0)
    line_count = analysis.metadata.get("line_count", 0)

    strategist = ComplexityStrategist()
    strategy_result = await strategist.execute(complexity_score=total_defs)
    strategy = strategy_result.data

    tracer.record(
        agent="ComplexityStrategist",
        decision_type="strategy_selection",
        rationale=f"Complexity score {total_defs} exceeds threshold.",
        chosen_action=strategy["strategy"],
        context={"line_count": line_count, "definitions": total_defs},
    )

    # =========================================================================
    # 4 & 5. THE ADAPTIVE LOOP (GENERATE + EVALUATE)
    # =========================================================================
    # Resolve project root for reading original source
    if config_service is not None:
        repo_root = Path(await config_service.get("REPO_PATH", required=True))
    else:
        async with context.registry.session() as session:
            runtime_config = await ConfigService.create(session)
            repo_root = Path(await runtime_config.get("REPO_PATH", required=True))

    original_code = (repo_root / rel_path_str).read_text(encoding="utf-8")

    # Prompt supports both single file fix and structural splitting
    current_prompt = (
        f"You are a Principal Software Engineer. Task: Reduce Cyclomatic Complexity via {strategy['strategy']}.\n"
        f"Instruction: {strategy['instruction']}\n\n"
        f"SOURCE CODE:\n{original_code}\n\n"
        "If the strategy requires splitting the file, return multiple code blocks using the format:\n"
        "[[write:path/to/file.py]]\n<code>\n[[/write]]\n"
        "Otherwise, return the updated Python code in ```python fences."
    )

    max_attempts = 3
    attempt = 0
    final_plan: dict[str, str] = {}  # Path -> Code mapping
    last_verdict = None

    while attempt < max_attempts:
        attempt += 1
        use_expert = attempt == max_attempts
        logger.info(
            "🔄 Attempt %d/%d (Expert Tier=%s)...", attempt, max_attempts, use_expert
        )

        try:
            # 4. PHASE: GENERATE
            coder = await context.cognitive_service.aget_client_for_role(
                "Coder", high_reasoning=use_expert
            )
            response_raw = await coder.make_request_async(
                current_prompt, user_id="complexity_unified"
            )

            # Support both Legacy Write Blocks and V2 code fences
            write_blocks = parse_write_blocks(response_raw)
            if write_blocks:
                # Scenario: Structural Split
                temp_plan = write_blocks
            else:
                # Scenario: In-place simplification
                extracted_code = (
                    extract_python_code_from_response(response_raw) or response_raw
                )
                temp_plan = {rel_path_str: extracted_code}

            # 5. PHASE: EVALUATE (Cross-file check)
            all_valid = True
            evaluator = ClarityEvaluator()

            # We evaluate the 'Primary' result (the original file or its main replacement)
            # against the original complexity.
            primary_new_code = temp_plan.get(rel_path_str) or next(
                iter(temp_plan.values())
            )

            last_verdict = await evaluator.execute(
                original_code=original_code, new_code=primary_new_code
            )

            if last_verdict.ok and last_verdict.data.get("is_better", False):
                logger.info("✅ Complexity reduction proven.")
                final_plan = temp_plan
                break
            else:
                reason = last_verdict.data.get(
                    "error", "No mathematical improvement measured"
                )
                logger.warning("⚠️  Attempt %d failed: %s. Retrying...", attempt, reason)
                current_prompt += f"\n\nCRITICAL FEEDBACK: Previous attempt failed. {reason}. Focus on modularity."

        except Exception as e:
            logger.error("🚨 API/Runtime Error during loop: %s", e)

    # =========================================================================
    # 6. PHASE: DECIDE
    # =========================================================================
    decider = GovernanceDecider()
    authorization = await decider.execute(
        evaluation_results=[last_verdict] if last_verdict else [],
        risk_tier="ELEVATED" if write else "ROUTINE",
    )

    # =========================================================================
    # 7. PHASE: EXECUTION
    # =========================================================================
    if authorization.data["can_proceed"] and final_plan:
        if not write:
            logger.info(
                "💡 [DRY RUN] Validated refactor ready for %d files.", len(final_plan)
            )
            return

        executor = ActionExecutor(context)
        logger.info("⚖️  Authorization Granted. Applying mutations...")

        # If we are splitting the file, we must delete the original first (Legacy behavior)
        if len(final_plan) > 1 or rel_path_str not in final_plan:
            await executor.execute("file.delete", write=True, file_path=rel_path_str)

        # Create/Update the resulting files
        for path, code in final_plan.items():
            await executor.execute("file.edit", write=True, file_path=path, code=code)

        duration = time.perf_counter() - start_time
        logger.info("✅ Complexity remediation successful in %.2fs", duration)
    else:
        blockers = authorization.data.get("blockers", ["No valid improvement produced"])
        logger.error("❌ EXECUTION HALTED: %s", ", ".join(blockers))
