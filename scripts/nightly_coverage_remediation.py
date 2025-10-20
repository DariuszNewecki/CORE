# scripts/nightly_coverage_remediation.py
"""
The orchestrator for the nightly autonomous coverage remediation job.

This script implements the "foreman" for the testing agent:
1. Ensures the local repository is clean and synchronized with the remote.
2. Checks if it is within its allowed operational time window (can be bypassed).
3. Analyzes the codebase to find files with low test coverage.
4. For each low-coverage file, it identifies "SIMPLE" functions as candidates.
5. It creates a prioritized queue of files to fix.
6. It invokes the `core-admin coverage remediate --file` command for each
   file in the queue, continuing until the time window ends or no simple
   targets remain.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

# --- THIS IS THE FIX: Ensure we can import from our project ---
# Add the project's 'src' directory to the Python path
project_root = Path(__file__).resolve().parents[1]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
# --- END OF FIX ---

from features.self_healing.coverage_analyzer import CoverageAnalyzer
from features.self_healing.test_target_analyzer import TestTargetAnalyzer
from shared.config import settings

console = Console()

# --- Configuration ---
START_HOUR = 22  # 10 PM
END_HOUR = 7  # 7 AM
MINIMUM_COVERAGE_TARGET = 75


def _ensure_clean_and_synced_workspace() -> bool:
    """
    Performs a pre-flight check to ensure the repo is clean and up-to-date.
    """
    console.print("[bold cyan]Step 0: Verifying workspace state...[/bold cyan]")
    try:
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
            cwd=settings.REPO_PATH,
        )
        if status_result.stdout.strip():
            console.print(
                "[bold red]❌ Error: Your workspace has uncommitted changes.[/bold red]"
            )
            console.print(
                "   Please commit or stash your changes before running the agent."
            )
            return False

        console.print("   -> Fetching latest changes from remote...")
        subprocess.run(
            ["git", "pull", "--rebase"],
            check=True,
            capture_output=True,
            text=True,
            cwd=settings.REPO_PATH,
        )
        console.print("[green]   -> ✅ Workspace is clean and up-to-date.[/green]")
        return True

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        console.print(f"[bold red]❌ Git command failed: {e}[/bold red]")
        if isinstance(e, subprocess.CalledProcessError):
            console.print(f"[red]{e.stderr}[/red]")
        return False


def _is_within_operating_window() -> bool:
    """Checks if the current time is within the allowed window."""
    current_hour = datetime.now().hour
    if START_HOUR > END_HOUR:
        return current_hour >= START_HOUR or current_hour < END_HOUR
    else:
        return START_HOUR <= current_hour < END_HOUR


def _get_low_coverage_files() -> list[tuple[str, float]]:
    """Gets a list of source files sorted by the lowest coverage first."""
    console.print("\n[bold cyan]Step 1: Analyzing current test coverage...[/bold cyan]")
    analyzer = CoverageAnalyzer()
    coverage_data = analyzer.get_module_coverage()

    if not coverage_data:
        console.print("[yellow]Could not retrieve coverage data. Aborting.[/yellow]")
        return []

    low_coverage = [
        (path, percent)
        for path, percent in coverage_data.items()
        if percent < MINIMUM_COVERAGE_TARGET and path.startswith("src/")
    ]
    low_coverage.sort(key=lambda item: item[1])
    console.print(f"   -> Found {len(low_coverage)} files below the coverage target.")
    return low_coverage


def _find_next_target(low_coverage_files: list[tuple[str, float]]) -> Path | None:
    """Finds the best next file to work on by looking for one with at least one "SIMPLE" test target."""
    console.print(
        "\n[bold cyan]Step 2: Finding a suitable file with 'SIMPLE' test targets...[/bold cyan]"
    )
    analyzer = TestTargetAnalyzer()
    for file_path_str, coverage in low_coverage_files:
        file_path = settings.REPO_PATH / file_path_str
        if not file_path.exists():
            continue
        targets = analyzer.analyze_file(file_path)
        if any(target.classification == "SIMPLE" for target in targets):
            console.print(
                f"   -> Found a great target: [green]{file_path_str}[/green] (Coverage: {coverage:.1f}%)"
            )
            return file_path
    console.print("[yellow]No more files with 'SIMPLE' test targets found.[/yellow]")
    return None


def _run_remediation_for_file(file_path: Path) -> bool:
    """Invokes the autonomous test generation for a single file."""
    console.print(
        f"\n[bold cyan]Step 3: Invoking autonomous agent for [green]{file_path.name}[/green]...[/bold cyan]"
    )
    command = [
        "poetry",
        "run",
        "core-admin",
        "coverage",
        "remediate",
        "--file",
        str(file_path),
    ]
    try:
        with subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=settings.REPO_PATH,
        ) as proc:
            if proc.stdout:
                for line in proc.stdout:
                    print(line, end="")
        return proc.returncode == 0
    except Exception as e:
        console.print(f"[bold red]   -> Error running remediation: {e}[/bold red]")
        return False


def main():
    """The main entry point for the nightly remediation script."""
    force_run = "--now" in sys.argv

    console.print(
        Panel(
            f"[bold green]🚀 Starting Autonomous Coverage Remediation[/bold green]\n"
            f"Operational Window: {START_HOUR}:00 - {END_HOUR}:00",
            expand=False,
        )
    )

    if not _ensure_clean_and_synced_workspace():
        console.print(
            Panel(
                "[bold red]❌ Pre-flight checks failed. Aborting run.[/bold red]",
                expand=False,
            )
        )
        return

    files_processed = 0
    while True:
        if not force_run and not _is_within_operating_window():
            console.print(
                f"\n[bold yellow]🕓 Current time is outside the operational window ({START_HOUR}:00 - {END_HOUR}:00). Halting run.[/bold yellow]"
            )
            break

        low_coverage_files = _get_low_coverage_files()
        if not low_coverage_files:
            console.print(
                "\n[bold green]✨ All files meet the coverage target! Nothing more to do.[/bold green]"
            )
            break

        target_file = _find_next_target(low_coverage_files)
        if not target_file:
            console.print(
                "\n[bold yellow]No more actionable targets found. Halting run.[/bold yellow]"
            )
            break

        success = _run_remediation_for_file(target_file)
        files_processed += 1

        if not success:
            console.print(
                f"[bold red]Remediation failed for {target_file.name}. Halting run to prevent further errors.[/bold red]"
            )
            break

        console.print(
            f"\n[bold]--- Cycle {files_processed} complete. Checking for next target... ---[/bold]\n"
        )

    console.print(
        Panel(
            f"[bold green]✅ Remediation Run Finished. Processed {files_processed} file(s).[/bold green]",
            expand=False,
        )
    )


if __name__ == "__main__":
    main()
