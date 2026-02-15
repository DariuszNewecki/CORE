# src/features/test_generation/helpers/test_executor.py

"""Test executor - generates, validates, and sandboxes single tests."""

from __future__ import annotations

import time
from typing import Any

from features.test_generation.artifacts import TestGenArtifactStore
from features.test_generation.helpers.context_extractor import ContextExtractor
from features.test_generation.llm_output import PythonOutputNormalizer
from features.test_generation.persistence import TestPersistenceService
from features.test_generation.prompt_engine import ConstitutionalTestPromptBuilder
from features.test_generation.sandbox import PytestSandboxRunner
from features.test_generation.validation import GeneratedTestValidator
from shared.component_primitive import ComponentResult
from shared.context import CoreContext
from shared.infrastructure.context.service import ContextService
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 695dc6f4-38b5-4124-8b8d-7f4359dfc54c
class TestExecutor:
    """Executes single test generation with validation and sandboxing."""

    def __init__(
        self,
        context: CoreContext,
        artifacts: TestGenArtifactStore,
        session_dir: str,
        normalizer: PythonOutputNormalizer,
        validator: GeneratedTestValidator,
        sandbox: PytestSandboxRunner,
        persistence: TestPersistenceService,
        prompt_engine: ConstitutionalTestPromptBuilder,
    ):
        self.context = context
        self.artifacts = artifacts
        self.session_dir = session_dir
        self.normalizer = normalizer
        self.validator = validator
        self.sandbox = sandbox
        self.persistence = persistence
        self.prompt_engine = prompt_engine
        self.extractor = ContextExtractor()

    # ID: f1f9b492-aff5-428d-8100-2e5a21cf57cb
    async def execute(
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
        """
        Generate, validate, and sandbox a single test.

        Args:
            file_path: Target file path
            symbol: Symbol dict with 'name' key
            strategy: Test generation strategy
            context_service: Context service for building context
            write: Whether to persist tests
            file_type: Type of file being tested
            complexity: Complexity level
            has_db_harness: Whether DB harness is available

        Returns:
            dict with test generation results
        """
        symbol_name = symbol.get("name", "<unknown>")

        try:
            # Build context package
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

            # Extract context information
            symbol_code = self.extractor.extract_target_code(
                context_packet, file_path, symbol_name
            )
            dependencies = self.extractor.extract_dependencies(context_packet)
            similar_symbols = self.extractor.extract_similar_symbols(context_packet)

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

            # Build prompt
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

            # Generate test via LLM
            cognitive_svc = await self.context.registry.get_cognitive_service()
            coder_client = await cognitive_svc.aget_client_for_role("Coder")

            raw = await coder_client.make_request_async(
                prompt, user_id="adaptive_test_gen"
            )
            self.artifacts.write_response(self.session_dir, symbol_name, raw)

            # Normalize output
            normalized = self.normalizer.normalize(raw)
            self.artifacts.write_normalized(
                self.session_dir, symbol_name, normalized.code, normalized.method
            )

            # Validate syntax
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
                    passing_test_names=sres.passed_tests,
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
