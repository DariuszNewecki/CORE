# src/features/self_healing/single_file_remediation.py

"""
Enhanced single-file test generation with comprehensive context analysis.

This version uses the EnhancedTestGenerator which gathers deep context
before generating tests, preventing misunderstandings and improving quality.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel

from features.self_healing.coverage_analyzer import CoverageAnalyzer
from mind.governance.audit_context import AuditorContext
from shared.config import settings
from shared.logger import getLogger
from src.features.self_healing.test_generator import EnhancedTestGenerator
from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)
console = Console()


# ID: 0c2cfe25-2da0-4aaa-8927-f1312c7a3825
class EnhancedSingleFileRemediationService:
    """
    Generates tests for a single file using comprehensive context analysis.

    Key improvements:
    1. Uses EnhancedTestGenerator with rich context
    2. Better error reporting and debugging
    3. Saves intermediate artifacts for analysis
    4. Filters by complexity threshold
    """

    def __init__(
        self,
        cognitive_service: CognitiveService,
        auditor_context: AuditorContext,
        file_path: Path,
        max_complexity: str = "SIMPLE",
    ):
        self.cognitive = cognitive_service
        self.auditor = auditor_context
        self.target_file = file_path
        self.analyzer = CoverageAnalyzer()
        self.generator = EnhancedTestGenerator(
            cognitive_service,
            auditor_context,
            use_iterative_fixing=False,
            max_complexity=max_complexity,
        )

    # ID: 840acb0f-7ec4-4f61-bc69-62c9b2fda26d
    async def remediate(self) -> dict[str, Any]:
        """
        Generate comprehensive tests for the target file.

        Returns:
            Dict with remediation results and metrics
        """
        console.print(
            "\n[bold cyan]🎯 Enhanced Single-File Test Generation[/bold cyan]"
        )
        console.print(f"   Target: {self.target_file}\n")
        if str(self.target_file).startswith(str(settings.REPO_PATH)):
            relative_path = self.target_file.relative_to(settings.REPO_PATH)
        else:
            relative_path = self.target_file
        target_str = str(relative_path)
        if "src/" in target_str:
            module_part = target_str.split("src/", 1)[1]
        else:
            module_part = target_str
        module_name = module_part.replace("/", ".").replace(".py", "")
        module_parts = module_name.split(".")
        if len(module_parts) > 1:
            test_dir = Path("tests") / module_parts[0]
        else:
            test_dir = Path("tests")
        test_filename = f"test_{Path(module_part).stem}.py"
        test_file = test_dir / test_filename
        goal = self._build_goal_description(relative_path)
        console.print("[bold]📊 Analysis Phase[/bold]")
        console.print(f"  Module: {module_name}")
        console.print(f"  Test file: {test_file}")
        console.print(f"  Goal: {goal}\n")
        try:
            console.print("[bold]🔬 Generating tests with enhanced context...[/bold]")
            result = await self.generator.generate_test(
                module_path=str(relative_path),
                test_file=str(test_file),
                goal=goal,
                target_coverage=75.0,
            )
            if result.get("status") == "success":
                console.print(
                    Panel(
                        f"✅ Test generation succeeded!\n\nTest file: {test_file}\nCoverage: {result.get('context_used', {}).get('coverage', 0):.1f}%\nUncovered functions: {result.get('context_used', {}).get('uncovered_functions', 0)}\nSimilar examples used: {result.get('context_used', {}).get('similar_examples', 0)}",
                        title="[bold green]Success[/bold green]",
                        border_style="green",
                    )
                )
                final_coverage = self._measure_final_coverage(str(relative_path))
                return {
                    "status": "completed",
                    "succeeded": 1,
                    "failed": 0,
                    "total": 1,
                    "test_file": str(test_file),
                    "final_coverage": final_coverage,
                }
            else:
                error_details = result.get("error", "Unknown error")
                test_result = result.get("test_result")
                if test_result and (not test_result.get("passed")):
                    error_details = f"Tests were generated but failed execution:\n\nReturn code: {test_result.get('returncode')}\n\n--- OUTPUT ---\n{test_result.get('output', '')}\n\n--- ERRORS ---\n{test_result.get('errors', '')}"
                console.print(
                    Panel(
                        error_details,
                        title="[bold red]❌ Generation Failed[/bold red]",
                        border_style="red",
                    )
                )
                return {
                    "status": "failed",
                    "succeeded": 0,
                    "failed": 1,
                    "total": 1,
                    "error": error_details,
                }
        except Exception as e:
            logger.error(f"Test generation failed: {e}", exc_info=True)
            console.print(f"[red]❌ Exception: {e}[/red]")
            return {
                "status": "failed",
                "succeeded": 0,
                "failed": 1,
                "total": 1,
                "error": str(e),
            }

    def _build_goal_description(self, module_path: Path) -> str:
        """Build a clear goal description for test generation."""
        module_name = module_path.stem
        return f"Create comprehensive unit tests for {module_name}. Focus on testing core functionality, edge cases, and error handling. Use appropriate mocks for external dependencies. Target 75%+ coverage with clear, maintainable tests."

    def _measure_final_coverage(self, module_path: str) -> float:
        """Measure coverage for the specific module after test generation."""
        try:
            coverage_data = self.analyzer.measure_coverage()
            if coverage_data and "files" in coverage_data:
                full_path = str(settings.REPO_PATH / module_path)
                for file_path, file_data in coverage_data["files"].items():
                    if module_path in file_path or full_path in file_path:
                        summary = file_data.get("summary", {})
                        percent_covered = summary.get("percent_covered", 0)
                        console.print(
                            f"\n[bold]Final Coverage for {module_path}: {percent_covered:.1f}%[/bold]"
                        )
                        return percent_covered
            overall = coverage_data.get("overall_percent", 0) if coverage_data else 0
            console.print(f"\n[bold]Overall Project Coverage: {overall:.1f}%[/bold]")
            return overall
        except Exception as e:
            logger.warning(f"Could not measure final coverage: {e}")
            return 0.0
