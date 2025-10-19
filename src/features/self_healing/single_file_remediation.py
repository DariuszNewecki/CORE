# src/features/self_healing/single_file_remediation.py
"""
Simple, targeted test generation for a single file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.cognitive_service import CognitiveService
from rich.console import Console
from shared.config import settings
from shared.logger import getLogger

from features.governance.audit_context import AuditorContext
from features.self_healing.coverage_analyzer import CoverageAnalyzer
from features.self_healing.test_generator import TestGenerator

log = getLogger(__name__)
console = Console()


@dataclass
# ID: ece1686e-2511-421a-a7eb-78303de4de4b
class TestGoal:
    """Represents a single test generation goal."""

    module: str
    test_file: str
    priority: int
    current_coverage: float
    target_coverage: float
    goal: str


# ID: cd1de13c-3197-40ed-a332-3bc4a1eb3922
class SingleFileRemediationService:
    """
    Generates tests for a single specific file.

    This is the simple path: one file → one goal → generate → done.
    No strategic analysis, no batching, no complex orchestration.
    """

    def __init__(
        self,
        cognitive_service: CognitiveService,
        auditor_context: AuditorContext,
        file_path: Path,
    ):
        self.cognitive = cognitive_service
        self.auditor = auditor_context
        self.target_file = file_path
        self.analyzer = CoverageAnalyzer()
        self.generator = TestGenerator(cognitive_service, auditor_context)

    # ID: c8b1c34f-27b4-46ec-8c34-b8ba516d122e
    async def remediate(self) -> dict[str, Any]:
        """
        Generate tests for the target file.

        Returns:
            Dict with remediation results
        """
        console.print("\n[bold cyan]🎯 Single File Coverage Remediation[/bold cyan]")
        console.print(f"   Target: {self.target_file}\n")

        # Convert Path to module name (handle absolute paths)
        target_str = str(self.target_file)

        # If it's an absolute path, extract just the part after 'src/'
        if "src/" in target_str:
            target_str = target_str.split("src/", 1)[1]

        module_name = target_str.replace("/", ".").replace(".py", "")

        # Determine the relative module path for test generation
        # TestGenerator needs the path relative to repo root
        if str(self.target_file).startswith(str(settings.REPO_PATH)):
            relative_path = self.target_file.relative_to(settings.REPO_PATH)
        else:
            relative_path = Path(target_str)

        # Determine test file path based on module structure
        # e.g., core.config_service -> tests/core/test_config_service.py
        module_parts = module_name.split(".")
        if len(module_parts) > 1:
            test_dir = "tests/" + "/".join(module_parts[:-1])
            test_filename = f"test_{module_parts[-1]}.py"
            test_file_path = f"{test_dir}/{test_filename}"
        else:
            test_file_path = f"tests/test_{self.target_file.stem}.py"

        # Create test goal
        goal = TestGoal(
            module=module_name,
            test_file=test_file_path,
            priority=1,
            current_coverage=0.0,
            target_coverage=80.0,
            goal=f"Generate comprehensive tests for {module_name}",
        )

        console.print(f"[green]✅ Target: {module_name}[/green]\n")

        # Generate test
        try:
            result = await self.generator.generate_test(
                module_path=str(relative_path),
                test_file=goal.test_file,
                goal=goal.goal,
                target_coverage=goal.target_coverage,
            )

            if result.get("status") == "success":
                console.print("[green]✅ Test generated successfully[/green]")

                # Measure final coverage
                final_coverage = self._measure_final_coverage()

                return {
                    "status": "completed",
                    "succeeded": 1,
                    "failed": 0,
                    "total": 1,
                    "final_coverage": final_coverage,
                }
            else:
                error = result.get("error", "Unknown error")
                console.print(f"[red]❌ Generation failed: {error}[/red]")
                return {
                    "status": "failed",
                    "succeeded": 0,
                    "failed": 1,
                    "total": 1,
                    "error": error,
                }

        except Exception as e:
            log.error(f"Test generation failed: {e}", exc_info=True)
            console.print(f"[red]❌ Exception: {e}[/red]")
            return {
                "status": "failed",
                "succeeded": 0,
                "failed": 1,
                "total": 1,
                "error": str(e),
            }

    def _measure_final_coverage(self) -> float:
        """Measure final coverage percentage."""
        coverage_data = self.analyzer.measure_coverage()
        if coverage_data:
            percent = coverage_data.get("overall_percent", 0)
            console.print(f"\n[bold]Final Project Coverage: {percent}%[/bold]")
            return percent
        return 0.0
