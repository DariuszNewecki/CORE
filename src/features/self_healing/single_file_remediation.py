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
from rich.panel import Panel
from shared.config import settings
from shared.logger import getLogger

from features.governance.audit_context import AuditorContext
from features.self_healing.coverage_analyzer import CoverageAnalyzer
from features.self_healing.test_generator import TestGenerator

log = getLogger(__name__)
console = Console()


@dataclass
# ID: 97d95d4a-8d23-4db5-9f36-71d35226db00
class TestGoal:
    """Represents a single test generation goal."""

    module: str
    test_file: str
    priority: int
    current_coverage: float
    target_coverage: float
    goal: str


# ID: 5a1ac32f-a8e6-43bd-a646-3d614918a3cd
class SingleFileRemediationService:
    """
    Generates tests for a single specific file.
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

    # ID: 0b904618-b389-4f9a-bd98-24fbf5e11e25
    async def remediate(self) -> dict[str, Any]:
        """
        Generate tests for the target file.
        """
        console.print("\n[bold cyan]🎯 Single File Coverage Remediation[/bold cyan]")
        console.print(f"   Target: {self.target_file}\n")

        target_str = str(self.target_file)
        if "src/" in target_str:
            target_str = target_str.split("src/", 1)[1]

        module_name = target_str.replace("/", ".").replace(".py", "")

        if str(self.target_file).startswith(str(settings.REPO_PATH)):
            relative_path = self.target_file.relative_to(settings.REPO_PATH)
        else:
            relative_path = Path(target_str)

        module_parts = module_name.split(".")
        if len(module_parts) > 1:
            test_dir = "tests/" + "/".join(module_parts[:-1])
            test_filename = f"test_{module_parts[-1]}.py"
            test_file_path = f"{test_dir}/{test_filename}"
        else:
            test_file_path = f"tests/test_{self.target_file.stem}.py"

        goal = TestGoal(
            module=str(
                relative_path
            ),  # Pass the relative path as the module identifier
            test_file=test_file_path,
            priority=1,
            current_coverage=0.0,
            target_coverage=80.0,
            goal=f"Generate comprehensive tests for {module_name}",
        )

        console.print(f"[green]✅ Target Module: {goal.module}[/green]\n")

        try:
            result = await self.generator.generate_test(
                module_path=goal.module,
                test_file=goal.test_file,
                goal=goal.goal,
                target_coverage=goal.target_coverage,
            )

            if result.get("status") == "success":
                console.print(
                    "[green]✅ Test generated and passed successfully[/green]"
                )
                final_coverage = self._measure_final_coverage()
                return {
                    "status": "completed",
                    "succeeded": 1,
                    "failed": 0,
                    "total": 1,
                    "final_coverage": final_coverage,
                }
            else:
                # --- THIS IS THE FIX ---
                # Provide a much more detailed error report.
                error_details = "Unknown error"
                test_result = result.get("test_result")
                if test_result:
                    error_details = (
                        f"Test execution failed with code {test_result.get('returncode')}.\n"
                        f"--- STDOUT ---\n{test_result.get('output')}\n"
                        f"--- STDERR ---\n{test_result.get('errors')}"
                    )
                else:
                    error_details = result.get("error", "Unknown error")

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
                # --- END OF FIX ---

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
