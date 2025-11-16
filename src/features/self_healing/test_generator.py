# src/features/self_healing/test_generator.py

"""
Enhanced test generation with comprehensive context analysis and iterative fixing.

This version gathers deep context about modules before generating tests,
preventing misunderstandings and improving quality. It also includes retry
logic to automatically fix failing tests.
"""

from __future__ import annotations

import ast
import asyncio
import re
from pathlib import Path
from typing import Any

from mind.governance.audit_context import AuditorContext
from services.context import ContextBuilder
from services.context.providers import ASTProvider, DBProvider, VectorProvider
from services.database.session_manager import get_session
from shared.config import settings
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.prompt_pipeline import PromptPipeline
from will.orchestration.validation_pipeline import validate_code_async

from features.self_healing.iterative_test_fixer import IterativeTestFixer
from features.self_healing.test_context_analyzer import (
    ModuleContext,
    TestContextAnalyzer,
)

logger = getLogger(__name__)


# ID: eda33d7a-e66e-4bfe-925d-d4438333d36d
class EnhancedTestGenerator:
    """
    Generates high-quality tests using comprehensive module analysis.

    Key improvements:
    1. Gathers rich context about module purpose and structure
    2. Identifies what needs mocking with specific examples
    3. Provides similar test examples from codebase
    4. Focuses on uncovered functions specifically
    5. Automatically retries and fixes failing tests (Phase 2)
    6. Uses ContextPackage for governed, rich context (NEW)
    """

    def __init__(
        self,
        cognitive_service: CognitiveService,
        auditor_context: AuditorContext,
        use_iterative_fixing: bool = True,
        max_fix_attempts: int = 3,
        max_complexity: str = "MODERATE",
    ):
        from features.self_healing.complexity_filter import ComplexityFilter

        self.cognitive = cognitive_service
        self.auditor = auditor_context
        self.pipeline = PromptPipeline(repo_path=settings.REPO_PATH)
        self.context_analyzer = TestContextAnalyzer()
        self.complexity_filter = ComplexityFilter(max_complexity=max_complexity)
        self.use_iterative_fixing = use_iterative_fixing
        if use_iterative_fixing:
            self.iterative_fixer = IterativeTestFixer(
                cognitive_service, auditor_context, max_attempts=max_fix_attempts
            )
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        """Load the enhanced test generation prompt."""
        prompt_path = settings.get_path("mind.prompts.test_generator")
        if not prompt_path or not prompt_path.exists():
            raise FileNotFoundError("Test generator prompt not found in meta.yaml")
        return prompt_path.read_text(encoding="utf-8")

    # ID: d156f0a7-2d3b-40d9-8d24-7d24fd7d16c3
    async def generate_test(
        self, module_path: str, test_file: str, goal: str, target_coverage: float
    ) -> dict[str, Any]:
        """
        Generate a test file with comprehensive context analysis.

        Args:
            module_path: Path to module to test (e.g., "src/core/prompt_pipeline.py")
            test_file: Path where test should be written
            goal: High-level goal for the tests
            target_coverage: Target coverage percentage

        Returns:
            Result dict with status and details
        """
        try:
            logger.info(f"Starting enhanced test generation for {module_path}")
            full_path = settings.REPO_PATH / module_path
            complexity_check = self.complexity_filter.should_attempt(full_path)
            if not complexity_check["should_attempt"]:
                logger.warning(f"Skipping {module_path}: {complexity_check['reason']}")
                return {
                    "status": "skipped",
                    "reason": complexity_check["reason"],
                    "complexity": complexity_check["complexity"],
                    "message": "File too complex for current threshold. Try with max_complexity='COMPLEX'",
                }
            logger.info(f"Complexity check passed: {complexity_check['reason']}")
            logger.info("Phase 1: Analyzing module context with ContextPackage...")
            try:
                context_packet = await self._build_context_package(module_path)
                logger.info(
                    f"✓ Using ContextPackage with {len(context_packet['context'])} items"
                )
                context = self._convert_packet_to_module_context(
                    context_packet, module_path
                )
            except Exception as e:
                logger.warning(f"ContextPackage failed, using legacy analyzer: {e}")
                context = await self.context_analyzer.analyze_module(module_path)
            if self.use_iterative_fixing:
                logger.info("Using iterative test fixing with retry logic...")
                return await self.iterative_fixer.generate_with_retry(
                    module_context=context,
                    test_file=test_file,
                    goal=goal,
                    target_coverage=target_coverage,
                )
            logger.info("Using single-shot generation (no retry)")
            return await self._generate_single_shot(
                context, test_file, goal, target_coverage
            )
        except Exception as e:
            logger.error(f"Test generation failed: {e}", exc_info=True)
            return {"status": "failed", "error": str(e)}

    async def _build_context_package(self, module_path: str) -> dict[str, Any]:
        """
        Build ContextPackage for the target module.

        Provides rich, governed context including:
        - Full function code (not just signatures)
        - Related symbols from DB
        - Constitutional redaction applied

        Args:
            module_path: Path to module

        Returns:
            ContextPackage dict
        """
        logger.info(f"Building ContextPackage for: {module_path}")
        full_path = settings.REPO_PATH / module_path
        source_code = full_path.read_text(encoding="utf-8")
        tree = ast.parse(source_code)
        target_functions = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    target_functions.append(node.name)
        module_name = (
            module_path.replace("src/", "").replace(".py", "").replace("/", ".")
        )
        task_spec = {
            "task_id": f"test_gen_{module_path.replace('/', '_')}",
            "task_type": "test.generate",
            "target_file": module_path,
            "target_symbol": target_functions[0] if target_functions else None,
            "summary": f"Generate tests for {module_path}",
            "scope": {
                "include": [module_name],
                "exclude": ["tests/*", "*.pyc"],
                "roots": [module_name.split(".")[0]],
            },
            "constraints": {"max_tokens": 50000, "max_items": 30},
        }
        async with get_session() as db:
            db_provider = DBProvider(db_service=db)
            ast_provider = ASTProvider(project_root=str(settings.REPO_PATH))
            vector_provider = VectorProvider()
            builder = ContextBuilder(
                db_provider=db_provider,
                vector_provider=vector_provider,
                ast_provider=ast_provider,
                config={"max_tokens": 50000, "max_context_items": 30},
            )
            packet = await builder.build_for_task(task_spec)
        logger.info(
            f"Built packet with {len(packet['context'])} context items, {packet['provenance']['build_stats']['tokens_total']} tokens"
        )
        return packet

    def _convert_packet_to_module_context(
        self, packet: dict, module_path: str
    ) -> ModuleContext:
        """
        Convert ContextPackage to legacy ModuleContext format.

        Extracts data from packet and fills in gaps with basic AST parsing.

        Args:
            packet: ContextPackage dict
            module_path: Target module path

        Returns:
            ModuleContext for backward compatibility
        """
        context_items = packet.get("context", [])
        functions = []
        for item in context_items:
            if item.get("item_type") in ("code", "symbol"):
                content = item.get("content", "")
                functions.append(
                    {
                        "name": item.get("name"),
                        "docstring": item.get("summary", ""),
                        "is_private": item.get("name", "").startswith("_"),
                        "is_async": "async def" in content,
                        "args": [],
                        "code": content,
                    }
                )
        full_path = settings.REPO_PATH / module_path
        source_code = full_path.read_text(encoding="utf-8")
        tree = ast.parse(source_code)
        return ModuleContext(
            module_path=module_path,
            module_name=Path(module_path).stem,
            import_path=module_path.replace("src/", "")
            .replace(".py", "")
            .replace("/", "."),
            source_code=source_code,
            module_docstring=ast.get_docstring(tree),
            classes=[],
            functions=functions,
            imports=[],
            dependencies=[],
            current_coverage=0.0,
            uncovered_lines=[],
            uncovered_functions=[f["name"] for f in functions],
            similar_test_files=[],
            external_deps=[],
            filesystem_usage=False,
            database_usage=False,
            network_usage=False,
        )

    async def _generate_single_shot(
        self, context: ModuleContext, test_file: str, goal: str, target_coverage: float
    ) -> dict[str, Any]:
        """
        Single-shot generation without retry (original behavior).

        This is kept as fallback or for comparison.
        """
        from rich.console import Console

        console = Console()
        try:
            logger.info("Phase 2: Building enriched prompt...")
            prompt = self._build_enriched_prompt(context, goal, target_coverage)
            debug_dir = settings.REPO_PATH / "work" / "testing" / "prompts"
            debug_dir.mkdir(parents=True, exist_ok=True)
            debug_file = debug_dir / f"{Path(test_file).stem}_prompt.txt"
            debug_file.write_text(prompt, encoding="utf-8")
            logger.info(f"Saved prompt to {debug_file}")
            logger.info("Phase 3: Generating test code...")
            client = await self.cognitive.aget_client_for_role("Coder")
            response = await client.make_request_async(
                prompt, user_id="test_generator_enhanced"
            )
            test_code = self._extract_code_block(response)
            if not test_code:
                preview = (response or "")[:500]
                logger.error(f"No code block found. Response preview: {preview}")
                fail_dir = settings.REPO_PATH / "reports" / "failed_test_generation"
                fail_dir.mkdir(parents=True, exist_ok=True)
                fail_file = fail_dir / f"{Path(test_file).stem}_response.txt"
                fail_file.write_text(response or "", encoding="utf-8")
                return {
                    "status": "failed",
                    "error": "No code block in LLM response",
                    "response_preview": preview,
                }
            logger.info("Phase 4: Validating generated code...")
            validation_result = await validate_code_async(
                test_file, test_code, auditor_context=self.auditor
            )
            if validation_result.get("status") == "dirty":
                violations = validation_result.get("violations", [])
                logger.warning(f"Validation failed for {test_file}: {violations}")
                fail_dir = settings.REPO_PATH / "reports" / "failed_test_generation"
                fail_dir.mkdir(parents=True, exist_ok=True)
                fail_file = fail_dir / f"failed_{Path(test_file).name}"
                fail_file.write_text(test_code, encoding="utf-8")
                logger.error(f"Saved invalid code to {fail_file}")
                return {
                    "status": "failed",
                    "error": "Validation failed",
                    "violations": violations,
                }
            test_path = settings.REPO_PATH / test_file
            test_path.parent.mkdir(parents=True, exist_ok=True)
            test_path.write_text(
                validation_result.get("code", test_code), encoding="utf-8"
            )
            logger.info(f"Wrote test file to {test_path}")
            logger.info("Phase 5: Running generated tests...")
            test_result = await self._run_test_async(test_file)
            success = test_result["passed"]
            logger.info(f"Test execution: {('PASSED' if success else 'FAILED')}")
            return {
                "status": "success" if success else "failed",
                "goal": goal,
                "test_file": test_file,
                "test_result": test_result,
                "context_used": {
                    "coverage": context.current_coverage,
                    "uncovered_functions": len(context.uncovered_functions),
                    "similar_examples": len(context.similar_test_files),
                },
            }
        except Exception as e:
            logger.error(f"Single-shot generation failed: {e}", exc_info=True)
            return {"status": "failed", "error": str(e)}

    def _build_enriched_prompt(
        self, context: ModuleContext, goal: str, target_coverage: float
    ) -> str:
        """
        Build a prompt enriched with comprehensive module context.

        This is the KEY improvement - we provide much more context to prevent
        misunderstandings like testing "HTML headers" vs "file headers".
        """
        base_prompt = self.prompt_template.format(
            module_path=context.module_path,
            import_path=context.import_path,
            target_coverage=target_coverage,
            module_code=context.source_code,
            goal=goal,
            safe_module_name=context.module_name,
        )
        enriched_prompt = f"# CRITICAL CONTEXT - READ THIS FIRST\n\n{context.to_prompt_context()}\n\n---\n\n{base_prompt}\n\n---\n\n# REMINDER: Focus Areas\n\nBased on the analysis above, prioritize testing these uncovered functions:\n{chr(10).join(f'- {func}' for func in context.uncovered_functions[:10])}\n\nRemember:\n1. The module purpose is: {context.module_docstring or 'See source code above'}\n2. Mock these external dependencies: {(', '.join(context.external_deps) if context.external_deps else 'None')}\n3. {('Use tmp_path for filesystem operations' if context.filesystem_usage else 'No filesystem operations detected')}\n4. Use the test patterns from similar modules shown above as examples\n\nGenerate ONLY the test code in a single Python code block.\n"
        return self.pipeline.process(enriched_prompt)

    def _extract_code_block(self, response: str) -> str | None:
        """Extract Python code from LLM response."""
        if not response:
            return None
        patterns = [
            "```python\\s*(.*?)\\s*```",
            "```\\s*python\\s*(.*?)\\s*```",
            "```\\s*(.*?)\\s*```",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            if matches:
                code = matches[0].strip()
                if code and len(code) > 50:
                    return code
        if response.strip().startswith(("import ", "from ", "def ", "class ", "#")):
            return response.strip()
        return None

    async def _run_test_async(self, test_file: str) -> dict[str, Any]:
        """Execute the generated test file."""
        try:
            process = await asyncio.create_subprocess_exec(
                "pytest",
                str(settings.REPO_PATH / test_file),
                "-v",
                "--tb=short",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=settings.REPO_PATH,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)
            output = stdout.decode("utf-8")
            errors = stderr.decode("utf-8")
            passed = process.returncode == 0
            return {
                "passed": passed,
                "returncode": process.returncode,
                "output": output,
                "errors": errors,
            }
        except TimeoutError:
            logger.error(f"Test execution timed out for {test_file}")
            return {
                "passed": False,
                "returncode": -1,
                "output": "",
                "errors": "Test execution timed out after 60 seconds",
            }
        except Exception as e:
            logger.error(f"Failed to run test {test_file}: {e}", exc_info=True)
            return {"passed": False, "returncode": -1, "output": "", "errors": str(e)}
