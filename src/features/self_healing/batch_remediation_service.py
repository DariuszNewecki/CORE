# src/features/self_healing/batch_remediation_service.py

"""
Batch test generation service for processing multiple files efficiently.

Selects files by lowest coverage and complexity threshold, processes them
in order, and provides progress reporting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mind.governance.audit_context import AuditorContext
from rich.console import Console
from rich.table import Table
from shared.config import settings
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService

from features.self_healing.coverage_analyzer import CoverageAnalyzer
from features.self_healing.single_file_remediation import (
    EnhancedSingleFileRemediationService,
)

logger = getLogger(__name__)
console = Console()


# ID: 6d9e1303-f11b-41c0-8897-d5016854a74d
class BatchRemediationService:
    """
    Processes multiple files for test generation in a single run.

    Strategy:
    1. Get all files with coverage data
    2. Filter by complexity threshold
    3. Sort by lowest coverage first (biggest wins)
    4. Process up to N files
    5. Report results
    """

    def __init__(
        self,
        cognitive_service: CognitiveService,
        auditor_context: AuditorContext,
        max_complexity: str = "MODERATE",
    ):
        from features.self_healing.complexity_filter import ComplexityFilter

        self.cognitive = cognitive_service
        self.auditor = auditor_context
        self.max_complexity = max_complexity
        self.analyzer = CoverageAnalyzer()
        self.complexity_filter = ComplexityFilter(max_complexity=max_complexity)

    # ID: 1b9a6db1-2cca-4410-b232-79edbd3d9809
    async def process_batch(self, count: int) -> dict[str, Any]:
        """
        Process N files for test generation.

        Args:
            count: Number of files to process

        Returns:
            Batch results with summary
        """
        console.print("[bold]🔍 Step 1: Finding candidate files...[/bold]\n")
        candidates = self._get_candidate_files()
        if not candidates:
            console.print("[yellow]No suitable files found for testing[/yellow]")
            return {"status": "no_candidates", "processed": 0, "results": []}
        console.print(f"Found {len(candidates)} files below 75% coverage")
        console.print(f"Filtering by complexity: {self.max_complexity}\n")
        filtered = self._filter_by_complexity(candidates)
        if not filtered:
            console.print(
                f"[yellow]No files match complexity threshold: {self.max_complexity}[/yellow]"
            )
            console.print("Try with --complexity moderate or --complexity complex")
            return {"status": "no_matches", "processed": 0, "results": []}
        console.print(f"✅ {len(filtered)} files match complexity threshold\n")
        to_process = filtered[:count]
        console.print(
            f"[bold]📝 Step 2: Processing {len(to_process)} files...[/bold]\n"
        )
        results = []
        for i, (file_path, coverage) in enumerate(to_process, 1):
            console.print(
                f"[cyan]File {i}/{len(to_process)}:[/cyan] {file_path} ({coverage:.1f}% coverage)"
            )
            result = await self._process_file(file_path)
            results.append(
                {"file": str(file_path), "original_coverage": coverage, **result}
            )
            console.print()
        self._print_summary(results)
        return {"status": "completed", "processed": len(results), "results": results}

    def _get_candidate_files(self) -> list[tuple[Path, float]]:
        """Get files with coverage data, sorted by lowest coverage first."""
        coverage_data = self.analyzer.get_module_coverage()
        if not coverage_data:
            return []
        candidates = [
            (settings.REPO_PATH / path, percent)
            for path, percent in coverage_data.items()
            if path.startswith("src/") and percent < 75.0
        ]
        candidates.sort(key=lambda x: x[1])
        return candidates

    def _filter_by_complexity(
        self, candidates: list[tuple[Path, float]]
    ) -> list[tuple[Path, float]]:
        """Filter candidates by complexity threshold."""
        print(f"DEBUG: Starting filter. Received {len(candidates)} candidates.")
        filtered = []
        for file_path, coverage in candidates:
            if not file_path.exists():
                print(
                    f"DEBUG: REJECTED {file_path.name} because file.exists() is False."
                )
                continue
            complexity_check = self.complexity_filter.should_attempt(file_path)
            if complexity_check["should_attempt"]:
                filtered.append((file_path, coverage))
                logger.debug(f"Accepted {file_path}: {complexity_check['reason']}")
            else:
                print(
                    f"DEBUG: REJECTED {file_path.name} by complexity filter: {complexity_check['reason']}"
                )
                logger.debug(f"Filtered {file_path}: {complexity_check['reason']}")
        return filtered

    async def _process_file(self, file_path: Path) -> dict[str, Any]:
        """Process a single file."""
        try:
            service = EnhancedSingleFileRemediationService(
                self.cognitive,
                self.auditor,
                file_path,
                max_complexity=self.max_complexity,
            )
            result = await service.remediate()
            test_result = result.get("test_result", {})
            if test_result:
                output = test_result.get("output", "")
                passed_count = self._count_passed(output)
                total_count = self._count_total(output)
                if total_count == 0:
                    passed = test_result.get("passed", False)
                    if passed:
                        console.print("  ✅ All tests passed!")
                        return {"status": "success", "tests_passed": True}
                    else:
                        console.print("  ❌ Tests failed (no count available)")
                        return {"status": "failed", "error": "Tests failed"}
                success_rate = (
                    passed_count / total_count * 100 if total_count > 0 else 0
                )
                if success_rate == 100:
                    console.print(
                        f"  ✅ All tests passed! ({total_count}/{total_count})"
                    )
                    return {"status": "success", "tests_passed": True}
                elif success_rate >= 50:
                    console.print(
                        f"  ✅ Partial success: {passed_count}/{total_count} tests ({success_rate:.0f}%)"
                    )
                    return {
                        "status": "partial",
                        "passed_count": passed_count,
                        "total_count": total_count,
                        "success_rate": success_rate,
                    }
                else:
                    console.print(
                        f"  ⚠️  Low success: {passed_count}/{total_count} tests ({success_rate:.0f}%)"
                    )
                    return {
                        "status": "low_success",
                        "passed_count": passed_count,
                        "total_count": total_count,
                        "success_rate": success_rate,
                    }
            if result.get("status") == "skipped":
                console.print(f"  ⏭️  Skipped: {result.get('reason', 'Unknown')}")
                return {"status": "skipped", "reason": result.get("reason")}
            console.print(f"  ❌ Failed: {result.get('error', 'Unknown error')}")
            return {"status": "failed", "error": result.get("error")}
        except Exception as e:
            console.print(f"  ❌ Error: {e}")
            logger.error(f"Failed to process {file_path}: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def _count_passed(self, pytest_output: str) -> int:
        """Extract passed test count from pytest output."""
        import re

        match = re.search("(\\d+) passed", pytest_output)
        return int(match.group(1)) if match else 0

    def _count_total(self, pytest_output: str) -> int:
        """Extract total test count from pytest output."""
        import re

        passed_match = re.search("(\\d+) passed", pytest_output)
        failed_match = re.search("(\\d+) failed", pytest_output)
        passed = int(passed_match.group(1)) if passed_match else 0
        failed = int(failed_match.group(1)) if failed_match else 0
        return passed + failed

    def _print_summary(self, results: list[dict]):
        """Print summary table of results."""
        console.print("\n[bold]📊 Batch Summary[/bold]\n")
        table = Table()
        table.add_column("File", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Tests", justify="right")
        table.add_column("Coverage", justify="right")
        success_count = 0
        partial_count = 0
        failed_count = 0
        skipped_count = 0
        for result in results:
            file_name = Path(result["file"]).name
            status = result.get("status", "unknown")
            if status == "success":
                status_str = "[green]✅ Success[/green]"
                tests_str = "All pass"
                success_count += 1
            elif status == "partial":
                status_str = "[yellow]⚠️  Partial[/yellow]"
                tests_str = f"{result['passed_count']}/{result['total_count']}"
                partial_count += 1
            elif status == "skipped":
                status_str = "[dim]⏭️  Skipped[/dim]"
                tests_str = "-"
                skipped_count += 1
            else:
                status_str = "[red]❌ Failed[/red]"
                tests_str = "-"
                failed_count += 1
            coverage_str = f"{result.get('original_coverage', 0):.1f}%"
            table.add_row(file_name, status_str, tests_str, coverage_str)
        console.print(table)
        console.print("\n[bold]Results:[/bold]")
        console.print(f"  ✅ Success: {success_count}")
        console.print(f"  ⚠️  Partial: {partial_count}")
        console.print(f"  ❌ Failed: {failed_count}")
        console.print(f"  ⏭️  Skipped: {skipped_count}")


# ID: c5a75c8a-9bb0-4513-9574-72b7b72bb295
async def remediate_batch(
    cognitive_service: CognitiveService,
    auditor_context: AuditorContext,
    count: int,
    max_complexity: str = "MODERATE",
) -> dict[str, Any]:
    """
    Entry point for batch remediation.

    Args:
        cognitive_service: AI service
        auditor_context: Audit context
        count: Number of files to process
        max_complexity: Complexity threshold

    Returns:
        Batch results
    """
    service = BatchRemediationService(
        cognitive_service, auditor_context, max_complexity=max_complexity
    )
    return await service.process_batch(count)
