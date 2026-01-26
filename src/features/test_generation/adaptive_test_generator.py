# src/features/test_generation/adaptive_test_generator.py

"""
Adaptive Test Generator - Constitutionally Governed Orchestrator.

ARCHITECTURE ALIGNMENT:
- Uses ContextService.build_for_task() for intelligent context gathering
- ContextPackage provides: target code, dependencies, similar symbols
- No theater - real semantic understanding via graph traversal + vectors
- Constitutional validation via simple code checks (not full audit)
- Governed persistence via FileHandler

KEY POLICY (V2.1):
- Unit/structural-first for sqlalchemy_model unless DB harness is detected.
- Sandbox is a scoring signal, not a hard gate.
- "Generated" means: normalized + validated test module produced.
- "Passing" means: sandbox pass.
- When --write is enabled: persist validated tests even if sandbox fails, but quarantine/mark clearly.

CONSTITUTIONAL FIX:
- Removed forbidden global import of 'get_session' (logic.di.no_global_session).
- Now uses the primed session factory from the ServiceRegistry via CoreContext.
- PROMPT BUILDING DELEGATED TO: prompt_engine.py
- PHASES MODULARIZED: parse_phase, load_phase, generation_phase
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


logger = getLogger(__name__)


@dataclass
# ID: 0b6d6382-c374-4ef6-bbdb-b6c8d0c54bf1
class TestGenerationResult:
    """Result of adaptive test generation for a file."""

    file_path: str
    total_symbols: int
    tests_generated: int  # Tier A: validated test module produced
    tests_failed: int  # Tier B: sandbox ran but failed (still a useful artifact)
    tests_skipped: int  # validation failures / missing symbol code
    success_rate: float  # Tier A rate (validated / total)
    strategy_switches: int
    patterns_learned: dict[str, int]
    total_duration: float
    generated_tests: list[dict[str, Any]]
    validation_failures: int = 0
    sandbox_passed: int = 0  # Tier C: sandbox passed count


# ID: 8af61f0d-92bc-42fc-b5e7-07bf15834183
class AdaptiveTestGenerator:
    """
    Constitutionally-governed test generator orchestrator.

    NO THEATER. Uses real infrastructure:
    - ContextService for semantic context building
    - Graph traversal for dependencies
    - Vector search for similar symbols (when available)
    - Constitutional-lite gating via deterministic validation
    """

    def __init__(self, context: CoreContext):
        self.context = context

        # Body Components
        self.file_analyzer = FileAnalyzer(context=context)
        self.symbol_extractor = SymbolExtractor(context=context)
        self.failure_evaluator = FailureEvaluator()

        # Will Components
        self.test_strategist = TestStrategist()

        # IO / Governance components
        self.file_handler = FileHandler(str(context.git_service.repo_path))
        self.artifacts = TestGenArtifactStore(self.file_handler)
        self.normalizer = PythonOutputNormalizer()
        self.validator = GeneratedTestValidator()
        self.sandbox = PytestSandboxRunner(
            self.file_handler, repo_root=str(context.git_service.repo_path)
        )
        self.persistence = TestPersistenceService(self.file_handler)

        # Harness detection
        self.harness_detector = HarnessDetector(context.git_service.repo_path)

        # Prompt engine
        self.prompt_engine = ConstitutionalTestPromptBuilder()

        # Artifact persistence session
        self.session_dir = self.artifacts.start_session().session_dir

        # Phase orchestration
        self.parse_phase = ParsePhase(context)
        self.load_phase = LoadPhase(context)

        # Test executor (used by generation phase)
        self.test_executor = TestExecutor(
            context=context,
            artifacts=self.artifacts,
            session_dir=self.session_dir,
            normalizer=self.normalizer,
            validator=self.validator,
            sandbox=self.sandbox,
            persistence=self.persistence,
            prompt_engine=self.prompt_engine,
        )

        # Generation phase
        self.generation_phase = GenerationPhase(
            test_strategist=self.test_strategist,
            failure_evaluator=self.failure_evaluator,
            test_executor=self.test_executor,
        )

    # ID: 270e60ff-9dbd-49c8-a752-a8f044b74e54
    async def generate_tests_for_file(
        self,
        file_path: str,
        write: bool = False,
        max_failures_per_pattern: int = 3,
    ) -> TestGenerationResult:
        """
        Generate tests for all symbols in a file with adaptive learning.

        Args:
            file_path: Relative path to target file
            write: Whether to persist tests to filesystem
            max_failures_per_pattern: Failures before switching strategy

        Returns:
            TestGenerationResult with statistics and generated tests
        """
        start_time = time.time()

        # Phase 1: Parse
        logger.info("📋 PHASE: Parse - Validating request structure...")
        if not await self.parse_phase.execute(file_path):
            return self._failed_result(file_path, "parse_phase_failed")

        # Phase 2: Load
        logger.info("📚 PHASE: Load - Initializing ContextService...")
        context_service = await self.load_phase.execute()
        if not context_service:
            return self._failed_result(file_path, "load_phase_failed")

        # Analyze file
        logger.info("🔍 Analyzing target file...")
        analysis = await self.file_analyzer.execute(file_path=file_path)
        if not analysis.ok:
            return self._failed_result(file_path, "analysis_failed")

        file_type = analysis.data.get("file_type", "unknown")
        complexity = analysis.data.get("complexity", "unknown")

        # Harness-aware policy
        harness = self.harness_detector.detect()
        logger.info(
            "🧰 Harness detection: db_harness=%s notes=%s",
            harness.has_db_harness,
            "; ".join(harness.notes) if harness.notes else "(none)",
        )

        # Select initial strategy
        logger.info("🎯 Selecting test generation strategy...")
        strategy = await self.test_strategist.execute(
            file_type=file_type, complexity=complexity
        )

        # Extract symbols
        logger.info("📦 Extracting symbols for test generation...")
        symbols_result = await self.symbol_extractor.execute(file_path=file_path)
        if not symbols_result.ok or not symbols_result.data.get("symbols"):
            return self._empty_result(file_path)

        symbols = symbols_result.data["symbols"]

        # Phase 3: Generate tests adaptively
        generation_result = await self.generation_phase.execute(
            file_path=file_path,
            symbols=symbols,
            initial_strategy=strategy,
            context_service=context_service,
            write=write,
            max_failures_per_pattern=max_failures_per_pattern,
            file_type=file_type,
            complexity=complexity,
            has_db_harness=harness.has_db_harness,
        )

        # Build final result
        result = TestGenerationResult(
            file_path=file_path,
            total_symbols=generation_result["total_symbols"],
            tests_generated=generation_result["tests_generated"],
            tests_failed=generation_result["tests_failed"],
            tests_skipped=generation_result["tests_skipped"],
            success_rate=generation_result["success_rate"],
            strategy_switches=generation_result["strategy_switches"],
            patterns_learned=generation_result["patterns_learned"],
            total_duration=time.time() - start_time,
            generated_tests=generation_result["generated_tests"],
            validation_failures=generation_result["validation_failures"],
            sandbox_passed=generation_result["sandbox_passed"],
        )

        # Write summary
        summary = {
            "file_path": result.file_path,
            "total_symbols": result.total_symbols,
            "tests_generated_validated": result.tests_generated,
            "tests_sandbox_passed": result.sandbox_passed,
            "tests_sandbox_failed": result.tests_failed,
            "tests_skipped": result.tests_skipped,
            "validated_rate": result.success_rate,
            "validation_failures": result.validation_failures,
            "strategy_switches": result.strategy_switches,
            "patterns_learned": result.patterns_learned,
            "duration_seconds": result.total_duration,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "artifacts_location": self.session_dir,
            "policy": {
                "unit_first_for_sqlalchemy_model": True,
                "sandbox_is_gate": False,
                "persist_validated_even_if_sandbox_fails": bool(write),
                "db_harness_detected": bool(harness.has_db_harness),
            },
        }
        self.artifacts.write_summary(self.session_dir, summary)

        logger.info("=" * 80)
        logger.info("📊 Session artifacts saved to: %s", self.session_dir)
        logger.info("=" * 80)

        return result

    def _failed_result(self, file_path: str, reason: str) -> TestGenerationResult:
        """Create result object for failed generation."""
        return TestGenerationResult(
            file_path=file_path,
            total_symbols=0,
            tests_generated=0,
            tests_failed=0,
            tests_skipped=0,
            success_rate=0.0,
            strategy_switches=0,
            patterns_learned={reason: 1},
            total_duration=0.0,
            generated_tests=[],
            validation_failures=0,
            sandbox_passed=0,
        )

    def _empty_result(self, file_path: str) -> TestGenerationResult:
        """Create result object for files with no symbols."""
        return TestGenerationResult(
            file_path=file_path,
            total_symbols=0,
            tests_generated=0,
            tests_failed=0,
            tests_skipped=0,
            success_rate=1.0,
            strategy_switches=0,
            patterns_learned={},
            total_duration=0.0,
            generated_tests=[],
            validation_failures=0,
            sandbox_passed=0,
        )
