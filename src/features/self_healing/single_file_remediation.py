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
        """
        console.print(
            "\n[bold cyan]🎯 Enhanced Single-File Test Generation[/bold cyan]"
        )
        console.print(f"   Target: {self.target_file}\n")

        # Make the path relative to repo root if needed
        if str(self.target_file).startswith(str(settings.REPO_PATH)):
            relative_path = self.target_file.relative_to(settings.REPO_PATH)
        else:
            relative_path = self.target_file

        target_str = str(relative_path)

        # Derive module part (strip leading 'src/' if present)
        if "src/" in target_str:
            module_part = target_str.split("src/", 1)[1]
        else:
            module_part = target_str

        module_name = module_part.replace("/", ".").replace(".py", "")
        module_parts = module_name.split(".")

        # Compute test file path
        if len(module_parts) > 1:
            test_dir = Path("tests") / module_parts[0]
        else:
            test_dir = Path("tests")
        test_filename = f"test_{Path(module_part).stem}.py"
        test_file = test_dir / test_filename

        goal = self._build_goal_description(module_name)

        console.print("[bold]📊 Analysis Phase[/bold]")
        console.print(f"  Module: {module_name}")
        console.print(f"  Test file: {test_file}")
        console.print(f"  Goal: {goal}\n")

        # --- Test generation + validation ------------------------------------
        try:
            console.print("[bold]🔬 Generating tests with enhanced context...[/bold]")

            result = await self.generator.generate_test(
                module_path=str(relative_path),
                test_file=str(test_file),
                goal=goal,
                target_coverage=75.0,
            )

        except Exception as exc:
            logger.error(
                "Unexpected error during enhanced single-file remediation for %s: %s",
                self.target_file,
                exc,
                exc_info=True,
            )
            console.print(
                Panel(
                    f"[bold red]❌ Unexpected error during test generation[/bold red]\n\n{exc}",
                    title="[bold red]Generation Error[/bold red]",
                    border_style="red",
                )
            )
            return {
                "status": "error",
                "file": str(self.target_file),
                "module": module_name,
                "test_file": str(test_file),
                "error": str(exc),
            }

        # Defensive: ensure result is a dict
        if not isinstance(result, dict):
            msg = (
                f"Generator returned unexpected result type: {type(result)!r}. "
                "Expected a dict."
            )
            logger.error(msg)
            console.print(
                Panel(
                    f"[bold red]❌ {msg}[/bold red]",
                    title="[bold red]Generation Error[/bold red]",
                    border_style="red",
                )
            )
            return {
                "status": "error",
                "file": str(self.target_file),
                "module": module_name,
                "test_file": str(test_file),
                "error": msg,
            }

        status = result.get("status")
        error_details = result.get("error")
        violations = result.get("violations") or []
        test_result = result.get("test_result") or {}

        # --- Happy path -------------------------------------------------------
        if status == "success":
            final_coverage = self._measure_final_coverage(str(relative_path))

            coverage_from_context = (
                result.get("context_used", {}).get("coverage")
                if isinstance(result.get("context_used"), dict)
                else None
            )
            uncovered_functions = (
                result.get("context_used", {}).get("uncovered_functions", 0)
                if isinstance(result.get("context_used"), dict)
                else 0
            )
            similar_examples = (
                result.get("context_used", {}).get("similar_examples", 0)
                if isinstance(result.get("context_used"), dict)
                else 0
            )

            coverage_line = ""
            if coverage_from_context is not None:
                coverage_line = (
                    f"Context coverage: {coverage_from_context:.1f}%\n"
                    f"Uncovered functions: {uncovered_functions}\n"
                    f"Similar examples used: {similar_examples}"
                )

            final_line = ""
            if final_coverage is not None:
                final_line = (
                    f"\nFinal coverage for {relative_path}: {final_coverage:.1f}%"
                )

            console.print(
                Panel(
                    f"✅ Test generation succeeded!\n\n"
                    f"Test file: {test_file}\n"
                    f"{coverage_line}{final_line}",
                    title="[bold green]Success[/bold green]",
                    border_style="green",
                )
            )

            return {
                "status": "completed",
                "succeeded": 1,
                "failed": 0,
                "total": 1,
                "file": str(self.target_file),
                "module": module_name,
                "test_file": str(test_file),
                "final_coverage": final_coverage,
                "raw_result": result,
            }

        # --- Partial success: tests created but some fail ----------------------
        if status == "tests_created_with_failures":
            execution_result = result.get("execution_result", {})
            output = execution_result.get("output", "")

            console.print(
                Panel(
                    "[bold yellow]⚠ Tests generated with some failures[/bold yellow]\n\n"
                    f"Test file: {test_file}\n"
                    f"Status: Tests were successfully generated but some failed when executed.\n\n"
                    "[dim]This is normal for LLM-generated tests. Review and fix the failing tests.[/dim]",
                    title="[bold yellow]Partial Success[/bold yellow]",
                    border_style="yellow",
                )
            )
            return {
                "status": "partial_success",
                "succeeded": 0,
                "failed": 0,
                "total": 1,
                "file": str(self.target_file),
                "module": module_name,
                "test_file": str(test_file),
                "execution_result": execution_result,
            }

        # --- Error path -----------------------------------------------------
        if not error_details:
            if status:
                error_details = f"Test generation failed with status '{status}'."
            else:
                error_details = "Test generation failed for unknown reasons."

        lines: list[str] = [
            f"[bold red]❌ Test generation failed for [cyan]{self.target_file}[/cyan][/bold red]",
            "",
            f"[bold]Reason:[/bold] {error_details}",
        ]

        # --- NEW: Show rejected code for debugging ---
        generated_code = result.get("code")
        if generated_code:
            lines.append("\n[bold]Generated Code (Preview):[/bold]")
            snippet = str(generated_code)
            if len(snippet) > 500:
                snippet = snippet[:500] + "\n... [truncated]"
            lines.append(f"[dim]{snippet}[/dim]")

        if violations:
            lines.append("\n[bold]Validation violations:[/bold]")
            for v in violations:
                if isinstance(v, dict):
                    rule = v.get("rule") or v.get("code") or "unknown"
                    severity = v.get("severity", "info")
                    message = v.get("message", "")
                    line_no = v.get("line")
                    loc = f" (line {line_no})" if line_no is not None else ""
                    lines.append(f"  • [{severity}] {rule}{loc}: {message}")
                else:
                    lines.append(f"  • {v}")

        if isinstance(test_result, dict):
            error_output = (
                test_result.get("errors")
                or test_result.get("output")
                or test_result.get("traceback")
            )
            if error_output:
                lines.append("\n[bold]Pytest output (truncated):[/bold]")
                snippet = str(error_output)
                if len(snippet) > 2000:
                    snippet = snippet[:2000] + "\n... [truncated]"
                lines.append(f"[dim]{snippet}[/dim]")

        console.print(
            Panel(
                "\n".join(lines),
                title="[bold red]Enhanced Single-File Remediation[/bold red]",
                border_style="red",
            )
        )

        return {
            "status": "failed",
            "file": str(self.target_file),
            "module": module_name,
            "test_file": str(test_file),
            "error": error_details,
            "violations": violations,
            "test_result": test_result,
            "raw_result": result,
        }

    def _build_goal_description(self, module_name: str) -> str:
        return (
            f"Create comprehensive unit tests for {module_name}. "
            "Focus on testing core functionality, edge cases, and error handling. "
            "Use appropriate mocks for external dependencies. "
            "Target 75%+ coverage with clear, maintainable tests."
        )

    def _measure_final_coverage(self, module_rel_path: str) -> float | None:
        try:
            coverage_data = self.analyzer.get_module_coverage()
            if not coverage_data:
                return None
            return coverage_data.get(module_rel_path)
        except Exception as exc:
            logger.debug(
                "Could not measure final coverage for %s: %s",
                module_rel_path,
                exc,
            )
            return None
