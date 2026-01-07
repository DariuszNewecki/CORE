# src/features/test_generation_v2/adaptive_test_generator.py

"""
Adaptive Test Generator - Constitutionally Governed with ContextService.

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
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from body.analyzers.file_analyzer import FileAnalyzer
from body.analyzers.symbol_extractor import SymbolExtractor
from body.evaluators.failure_evaluator import FailureEvaluator
from features.test_generation_v2.artifacts import TestGenArtifactStore
from features.test_generation_v2.harness_detection import HarnessDetector
from features.test_generation_v2.llm_output import PythonOutputNormalizer
from features.test_generation_v2.persistence import TestPersistenceService

# CONSTITUTIONAL FIX: Import modular prompt builder
from features.test_generation_v2.prompt_engine import ConstitutionalTestPromptBuilder
from features.test_generation_v2.sandbox import PytestSandboxRunner
from features.test_generation_v2.validation import GeneratedTestValidator
from shared.component_primitive import ComponentResult
from shared.context import CoreContext
from shared.infrastructure.context.service import ContextService
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
    Constitutionally-governed test generator using ContextService.

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

        # CONSTITUTIONAL FIX: Initialize the new prompt engine
        self.prompt_engine = ConstitutionalTestPromptBuilder()

        # Artifact persistence session
        self.session_dir = self.artifacts.start_session().session_dir

    # ID: 270e60ff-9dbd-49c8-a752-a8f044b74e54
    async def generate_tests_for_file(
        self,
        file_path: str,
        write: bool = False,
        max_failures_per_pattern: int = 3,
    ) -> TestGenerationResult:
        start_time = time.time()

        logger.info("📋 PHASE: Parse - Validating request structure...")
        if not await self._phase_parse(file_path):
            return self._failed_result(file_path, "parse_phase_failed")

        logger.info("📚 PHASE: Load - Initializing ContextService...")
        context_service = await self._phase_load()
        if not context_service:
            return self._failed_result(file_path, "load_phase_failed")

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

        logger.info("🎯 Selecting test generation strategy...")
        strategy = await self.test_strategist.execute(
            file_type=file_type, complexity=complexity
        )

        logger.info("📦 Extracting symbols for test generation...")
        symbols_result = await self.symbol_extractor.execute(file_path=file_path)
        if not symbols_result.ok or not symbols_result.data.get("symbols"):
            return self._empty_result(file_path)

        symbols = symbols_result.data["symbols"]

        result = await self._generate_tests_adaptively(
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

        result.total_duration = time.time() - start_time

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

    async def _phase_parse(self, file_path: str) -> bool:
        try:
            abs_path = self.context.git_service.repo_path / file_path
            if not abs_path.exists():
                logger.error("Parse Phase Failed: File does not exist: %s", file_path)
                return False

            if not abs_path.is_relative_to(self.context.git_service.repo_path):
                logger.error(
                    "Parse Phase Failed: File outside repository: %s", file_path
                )
                return False

            logger.info("✅ Parse Phase: Request validated")
            return True

        except Exception as e:
            logger.error("Parse Phase Failed: %s", e, exc_info=True)
            return False

    async def _phase_load(self) -> ContextService | None:
        """
        CONSTITUTIONAL FIX: Uses registry session factory to avoid global import.
        """
        try:
            cognitive_service = await self.context.registry.get_cognitive_service()

            qdrant_service = None
            try:
                qdrant_service = await self.context.registry.get_qdrant_service()
            except Exception:
                logger.warning("Qdrant not available - semantic search disabled")

            # Resolve session factory via the registry (primed by Sanctuary)

            context_service = ContextService(
                qdrant_client=qdrant_service,
                cognitive_service=cognitive_service,
                project_root=str(self.context.git_service.repo_path),
                # DI FIX: Use the late-binding factory from the registry
                session_factory=self.context.registry.session,
            )

            logger.info("✅ Load Phase: ContextService initialized")
            return context_service

        except Exception as e:
            logger.error("Load Phase Failed: %s", e, exc_info=True)
            return None

    async def _generate_tests_adaptively(
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
    ) -> TestGenerationResult:
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

        # Failure throttling by pattern (prevents wasting time)
        pattern_fail_counts: dict[str, int] = {}

        for i, symbol in enumerate(symbols, 1):
            symbol_name = symbol.get("name", "<unknown>")
            logger.info(
                "📝 [%d/%d] Generating test for: %s", i, len(symbols), symbol_name
            )

            test_result = await self._generate_single_test_with_context(
                file_path=file_path,
                symbol=symbol,
                strategy=current_strategy,
                context_service=context_service,
                write=write,
                file_type=file_type,
                complexity=complexity,
                has_db_harness=has_db_harness,
            )

            # CONSTITUTIONAL FIX: Added Adaptive Retry logic
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
                    test_result = await self._generate_single_test_with_context(
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

        return TestGenerationResult(
            file_path=file_path,
            total_symbols=len(symbols),
            tests_generated=validated_count,
            tests_failed=sandbox_failed,
            tests_skipped=skipped,
            success_rate=validated_count / len(symbols) if symbols else 0.0,
            strategy_switches=strategy_switches,
            patterns_learned=dict(Counter(pattern_history)),
            total_duration=0.0,
            generated_tests=generated_tests,
            validation_failures=validation_failures,
            sandbox_passed=sandbox_passed,
        )

    async def _generate_single_test_with_context(
        self,
        file_path: str,
        symbol: dict,
        strategy: ComponentResult,
        context_service: ContextService,
        write: bool,
        file_type: str,
        complexity: str,
        has_db_harness: bool,
    ) -> dict[str, Any]:
        symbol_name = symbol.get("name", "<unknown>")

        try:
            task_spec = {
                "task_id": f"test_gen_{symbol_name}_{int(time.time())}",
                "task_type": "test.generate",
                "target_file": file_path,
                "target_symbol": symbol_name,
                "summary": f"Generate test for {symbol_name} in {file_path}",
                "scope": {"traversal_depth": 2},
            }

            context_packet = await context_service.build_for_task(
                task_spec, use_cache=True
            )

            symbol_code = self._extract_target_code(
                context_packet, file_path, symbol_name
            )
            dependencies = self._extract_dependencies(context_packet)
            similar_symbols = self._extract_similar_symbols(context_packet)

            if not symbol_code:
                return {
                    "symbol": symbol_name,
                    "skipped": True,
                    "validation_failure": True,
                    "validated": False,
                    "sandbox_ran": False,
                    "sandbox_passed": False,
                    "persisted": False,
                    "error": "Could not extract symbol code from ContextPackage",
                }

            # CONSTITUTIONAL FIX: Call modularized prompt engine
            prompt = self.prompt_engine.build(
                symbol_name=symbol_name,
                symbol_code=symbol_code,
                dependencies=dependencies,
                similar_symbols=similar_symbols,
                strategy=strategy,
                file_type=file_type,
                complexity=complexity,
                has_db_harness=has_db_harness,
                context_packet=context_packet,
            )

            self.artifacts.write_prompt(self.session_dir, symbol_name, prompt)

            cognitive_svc = await self.context.registry.get_cognitive_service()
            coder_client = await cognitive_svc.aget_client_for_role("Coder")

            raw = await coder_client.make_request_async(
                prompt, user_id="adaptive_test_gen"
            )
            self.artifacts.write_response(self.session_dir, symbol_name, raw)

            normalized = self.normalizer.normalize(raw)
            self.artifacts.write_normalized(
                self.session_dir, symbol_name, normalized.code, normalized.method
            )

            vres = self.validator.validate(normalized.code)
            self.artifacts.write_validation(
                self.session_dir, symbol_name, vres.ok, vres.error, normalized.method
            )

            if not vres.ok:
                logger.warning("Validation failed: %s", vres.error)
                return {
                    "symbol": symbol_name,
                    "skipped": True,
                    "validation_failure": True,
                    "validated": False,
                    "sandbox_ran": False,
                    "sandbox_passed": False,
                    "persisted": False,
                    "test_code": normalized.code,
                    "error": f"Validation failed: {vres.error}",
                }

            self.artifacts.write_generated(
                self.session_dir, symbol_name, normalized.code
            )

            # Sandbox is a scoring signal (not a gate)
            sres = await self.sandbox.run(
                normalized.code, symbol_name, timeout_seconds=30
            )
            self.artifacts.write_sandbox(
                self.session_dir, symbol_name, sres.passed, sres.error
            )

            persisted = False
            persist_path = ""
            persist_error = ""

            # Policy: if --write, persist validated tests even if sandbox fails
            if write:
                pres = self.persistence.persist_quarantined(
                    original_file=file_path,
                    symbol_name=symbol_name,
                    test_code=normalized.code,
                    sandbox_passed=sres.passed,
                )
                persisted = pres.ok
                persist_path = pres.path
                persist_error = pres.error

            return {
                "symbol": symbol_name,
                "skipped": False,
                "validation_failure": False,
                "validated": True,
                "sandbox_ran": True,
                "sandbox_passed": sres.passed,
                "persisted": persisted,
                "persist_path": persist_path,
                "persist_error": persist_error,
                "test_code": normalized.code,
                "error": ("" if sres.passed else sres.error),
            }

        except Exception as e:
            logger.error(
                "Test generation failed for %s: %s", symbol_name, e, exc_info=True
            )
            return {
                "symbol": symbol_name,
                "skipped": False,
                "validation_failure": False,
                "validated": False,
                "sandbox_ran": False,
                "sandbox_passed": False,
                "persisted": False,
                "error": str(e),
            }

    def _extract_target_code(
        self, context_packet: dict[str, Any], file_path: str, symbol_name: str
    ) -> str:
        target_canon = Path(file_path).as_posix().lstrip("./")

        for item in context_packet.get("context", []):
            item_type = item.get("item_type")
            item_name = item.get("name", "")
            item_path_raw = item.get("path", "")

            if item_type in ("code", "symbol") and item_name == symbol_name:
                # Canonicalize item path
                item_canon = Path(item_path_raw).as_posix().lstrip("./")
                if target_canon == item_canon:
                    return item.get("content", "")

        # Fallback: find any code matching the file path if symbol-specific match failed
        for item in context_packet.get("context", []):
            if item.get("item_type") == "code":
                item_canon = Path(item.get("path", "")).as_posix().lstrip("./")
                if target_canon == item_canon:
                    return item.get("content", "")

        return ""

    def _extract_dependencies(self, context_packet: dict[str, Any]) -> list[dict]:
        dependencies: list[dict[str, str]] = []
        for item in context_packet.get("context", []):
            if item.get("item_type") == "import":
                dependencies.append(
                    {"name": item.get("name", ""), "path": item.get("path", "")}
                )
        return dependencies

    def _extract_similar_symbols(self, context_packet: dict[str, Any]) -> list[dict]:
        similar: list[dict[str, Any]] = []
        for item in context_packet.get("context", []):
            if item.get("item_type") == "symbol" and item.get("similarity", 0) > 0.7:
                similar.append(
                    {
                        "name": item.get("name", ""),
                        "code": (item.get("content", "") or "")[:500],
                        "summary": item.get("summary", ""),
                    }
                )
        return similar[:3]

    async def _read_target_file_for_tests(
        self, goal: str, target_file: str
    ) -> tuple[str | None, str | None]:
        """
        Extracts the module path from the goal and reads the file.
        """
        try:
            import re

            match = re.search(r"for\s+(src/[^\s]+\.py)", goal)
            if not match:
                return None, None

            module_path = match.group(1)
            full_path = self.context.git_service.repo_path / module_path

            if not full_path.exists():
                return None, None

            import asyncio

            content = await asyncio.to_thread(
                lambda: full_path.read_text(encoding="utf-8")
            )
            return content, module_path

        except Exception as e:
            logger.error("Failed to read target file: %s", e)
            return None, None

    def _failed_result(self, file_path: str, reason: str) -> TestGenerationResult:
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
