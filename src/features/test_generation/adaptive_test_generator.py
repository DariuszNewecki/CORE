# src/features/test_generation/adaptive_test_generator.py

"""
Adaptive Test Generator - Lean Orchestrator.
Refactored V2.4: Delegated intelligence and reporting to sub-neurons.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from body.analyzers.file_analyzer import FileAnalyzer
from body.analyzers.symbol_extractor import SymbolExtractor
from body.evaluators.failure_evaluator import FailureEvaluator
from features.test_generation.artifacts import TestGenArtifactStore
from features.test_generation.harness_detection import HarnessDetector
from features.test_generation.helpers import TestExecutor
from features.test_generation.llm_output import PythonOutputNormalizer
from features.test_generation.persistence import TestPersistenceService
from features.test_generation.phases import GenerationPhase, LoadPhase, ParsePhase
from features.test_generation.prompt_engine import ConstitutionalTestPromptBuilder
from features.test_generation.sandbox import PytestSandboxRunner
from features.test_generation.validation import GeneratedTestValidator
from shared.context import CoreContext
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from will.strategists.test_strategist import TestStrategist

from .result_aggregator import TestResultAggregator


logger = getLogger(__name__)


@dataclass
# ID: e9c6a8a6-d6b2-4453-80fc-5c556a892d53
class TestGenerationResult:
    file_path: str
    total_symbols: int
    tests_generated: int
    tests_failed: int
    tests_skipped: int
    success_rate: float
    strategy_switches: int
    patterns_learned: dict[str, int]
    total_duration: float
    generated_tests: list[dict[str, Any]]
    validation_failures: int = 0
    sandbox_passed: int = 0


# ID: 8af61f0d-92bc-42fc-b5e7-07bf15834183
class AdaptiveTestGenerator:
    """The Switchboard: Coordinates the test generation lifecycle."""

    def __init__(self, context: CoreContext):
        self.context = context
        repo_path = context.git_service.repo_path

        # Primitives
        self.file_handler = FileHandler(str(repo_path))
        self.artifacts = TestGenArtifactStore(self.file_handler)
        self.session_dir = self.artifacts.start_session().session_dir

        # Phases & Sub-Orchestrators
        self.parse_phase = ParsePhase(context)
        self.load_phase = LoadPhase(context)

        self.test_executor = TestExecutor(
            context=context,
            artifacts=self.artifacts,
            session_dir=self.session_dir,
            normalizer=PythonOutputNormalizer(),
            validator=GeneratedTestValidator(),
            sandbox=PytestSandboxRunner(self.file_handler, str(repo_path)),
            persistence=TestPersistenceService(self.file_handler),
            prompt_engine=ConstitutionalTestPromptBuilder(),
        )

        self.generation_phase = GenerationPhase(
            test_strategist=TestStrategist(),
            failure_evaluator=FailureEvaluator(),
            test_executor=self.test_executor,
        )

    # ID: 2c52f0ba-13f3-4893-b556-22a9a2aaa16e
    async def generate_tests_for_file(
        self, file_path: str, write: bool = False
    ) -> TestGenerationResult:
        start_time = time.time()

        # 1. PRE-FLIGHT (Parse & Load)
        if not await self.parse_phase.execute(file_path):
            return self._empty_fail(file_path)
        context_service = await self.load_phase.execute()

        # 2. ANALYSIS
        analysis = await FileAnalyzer(self.context).execute(file_path=file_path)
        harness = HarnessDetector(self.context.git_service.repo_path).detect()
        symbols = (
            await SymbolExtractor(self.context).execute(file_path=file_path)
        ).data.get("symbols", [])

        # 3. CORE GENERATION (Delegated)
        strategy = await TestStrategist().execute(analysis.data["file_type"])
        gen_data = await self.generation_phase.execute(
            file_path=file_path,
            symbols=symbols,
            initial_strategy=strategy,
            context_service=context_service,
            write=write,
            file_type=analysis.data["file_type"],
            has_db_harness=harness.has_db_harness,
            complexity=analysis.data["complexity"],
            max_failures_per_pattern=3,
        )

        # 4. AGGREGATION & REPORTING (Delegated to Aggregator)
        aggregator = TestResultAggregator()
        result = aggregator.build_final_result(
            file_path,
            gen_data["generated_tests"],
            start_time,
            gen_data["strategy_switches"],
            gen_data["patterns_learned"],
        )

        summary_payload = aggregator.format_summary_json(
            result, self.session_dir, harness
        )
        self.artifacts.write_summary(self.session_dir, summary_payload)

        return result

    def _empty_fail(self, path: str) -> TestGenerationResult:
        return TestResultAggregator.build_final_result(
            path, [], time.time(), 0, {"error": 1}
        )
