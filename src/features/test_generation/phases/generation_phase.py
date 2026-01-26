# src/features/test_generation/phases/generation_phase.py

"""Generation phase - adaptive test generation loop with learning."""

from __future__ import annotations

from collections import Counter
from typing import Any

from body.evaluators.failure_evaluator import FailureEvaluator
from features.test_generation.helpers import TestExecutor
from shared.component_primitive import ComponentResult
from shared.infrastructure.context.service import ContextService
from shared.logger import getLogger
from will.strategists.test_strategist import TestStrategist


logger = getLogger(__name__)


# ID: c3d4e5f6-a7b8-9c0d-1e2f-3a4b5c6d7e8f
class GenerationPhase:
    """Executes adaptive test generation loop with pattern learning."""

    def __init__(
        self,
        test_strategist: TestStrategist,
        failure_evaluator: FailureEvaluator,
        test_executor: TestExecutor,
    ):
        self.test_strategist = test_strategist
        self.failure_evaluator = failure_evaluator
        self.test_executor = test_executor

    # ID: 3cb6b5f1-bd7c-4e22-80eb-494db2abafce
    async def execute(
        self,
        file_path: str,
        symbols: list[dict],
        initial_strategy: ComponentResult,
        context_service: ContextService,
        write: bool,
        max_failures_per_pattern: int,
        file_type: str,
        complexity: str,
        has_db_harness: bool,
    ) -> dict[str, Any]:
        """
        Generate tests adaptively with pattern learning and strategy switching.

        Args:
            file_path: Target file path
            symbols: List of symbols to generate tests for
            initial_strategy: Starting test strategy
            context_service: Context service for building context packages
            write: Whether to persist tests
            max_failures_per_pattern: Failures before switching strategy
            file_type: Type of file being tested
            complexity: Complexity level
            has_db_harness: Whether DB test harness is available

        Returns:
            dict with generation statistics and results
        """
        logger.info("🔄 Beginning adaptive test generation loop...")

        current_strategy = initial_strategy
        pattern_history: list[str] = []
        strategy_switches = 0

        # Tiered counters
        validated_count = 0
        sandbox_passed = 0
        sandbox_failed = 0
        skipped = 0
        validation_failures = 0

        generated_tests: list[dict[str, Any]] = []

        for i, symbol in enumerate(symbols, 1):
            symbol_name = symbol.get("name", "<unknown>")
            logger.info(
                "🔍 [%d/%d] Generating test for: %s", i, len(symbols), symbol_name
            )

            test_result = await self.test_executor.execute(
                file_path=file_path,
                symbol=symbol,
                strategy=current_strategy,
                context_service=context_service,
                write=write,
                file_type=file_type,
                complexity=complexity,
                has_db_harness=has_db_harness,
            )

            # Adaptive retry logic
            if test_result.get("error") and not test_result.get("skipped"):
                error_msg = test_result.get("error", "Unknown error")
                eval_result = await self.failure_evaluator.execute(
                    error=error_msg,
                    pattern_history=pattern_history,
                )
                pattern = eval_result.data["pattern"]
                pattern_history = eval_result.metadata["pattern_history"]

                if eval_result.data.get("should_switch"):
                    logger.info(
                        "🔄 Pattern '%s' detected. RETRYING %s...", pattern, symbol_name
                    )
                    current_strategy = await self.test_strategist.execute(
                        file_type=file_type,
                        complexity=complexity,
                        failure_pattern=pattern,
                        pattern_count=eval_result.data["occurrences"],
                    )
                    strategy_switches += 1

                    # RETRY the same function with the new strategy
                    test_result = await self.test_executor.execute(
                        file_path=file_path,
                        symbol=symbol,
                        strategy=current_strategy,
                        context_service=context_service,
                        write=write,
                        file_type=file_type,
                        complexity=complexity,
                        has_db_harness=has_db_harness,
                    )

            # Always record attempt outcome for learning/traceability
            generated_tests.append(test_result)

            if test_result.get("skipped"):
                skipped += 1
                if test_result.get("validation_failure"):
                    validation_failures += 1
                continue

            if test_result.get("validated"):
                validated_count += 1

            if test_result.get("sandbox_passed"):
                sandbox_passed += 1
            elif test_result.get("sandbox_ran"):
                sandbox_failed += 1

        return {
            "total_symbols": len(symbols),
            "tests_generated": validated_count,
            "tests_failed": sandbox_failed,
            "tests_skipped": skipped,
            "success_rate": validated_count / len(symbols) if symbols else 0.0,
            "strategy_switches": strategy_switches,
            "patterns_learned": dict(Counter(pattern_history)),
            "generated_tests": generated_tests,
            "validation_failures": validation_failures,
            "sandbox_passed": sandbox_passed,
        }
