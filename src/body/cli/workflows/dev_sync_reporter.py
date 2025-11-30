# src/body/cli/workflows/dev_sync_reporter.py
"""
DevSyncReporter - User-facing reporting for dev-sync workflow.

Follows the same pattern as AuditRunReporter but for development synchronization.
Displays command results in a clean, structured format with phases and summary.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rich.console import Console
from rich.table import Table
from rich.text import Text
from shared.activity_logging import ActivityRun, log_activity
from shared.cli_types import CommandResult

# FIXED: Disable timestamps in console output for cleaner display
console = Console(log_time=False)


@dataclass
# ID: dev_sync_phase_v1
# ID: 08f90cdd-370c-4988-80e8-0ad64f73afe1
class DevSyncPhase:
    """Represents a logical phase in the dev-sync workflow."""

    name: str
    """Human-readable phase name (e.g., 'Fixers', 'Database Sync')"""

    results: list[CommandResult] = field(default_factory=list)
    """Commands executed in this phase"""

    @property
    # ID: 56b5b128-8286-48ef-942a-21b9da4a7a83
    def ok(self) -> bool:
        """Phase succeeds if all commands succeed."""
        return all(r.ok for r in self.results)

    @property
    # ID: 1258d2aa-3dd9-434c-a495-4e59d33bcbca
    def total_duration(self) -> float:
        """Sum of all command durations in this phase."""
        return sum(r.duration_sec for r in self.results)


@dataclass
# ID: dev_sync_reporter_v1
# ID: a6bd1a16-dae7-4acb-892c-e467f945870c
class DevSyncReporter:
    """
    Coordinates user-facing reporting for dev-sync workflow.

    Usage:
        with ActivityRun.create("dev.sync") as run:
            reporter = DevSyncReporter(run, repo_path=str(repo_root))
            reporter.print_header()

            # Phase 1: Fixers
            phase = reporter.start_phase("Fixers")
            result = await fix_ids_internal(write=True)
            reporter.record_result(result, phase)
            # ... more commands

            # Print results
            reporter.print_phases()
            reporter.print_summary()
    """

    run: ActivityRun
    repo_path: str
    phases: list[DevSyncPhase] = field(default_factory=list)
    current_phase: DevSyncPhase | None = None

    # ID: print_header_v1
    # ID: d62160fa-7cdb-4610-95f0-540394d8ea22
    def print_header(self) -> None:
        """Print workflow header with run metadata."""
        console.rule("[bold]CORE Dev Sync Workflow[/bold]")
        console.print("[bold]Workflow[/bold] : dev.sync")
        console.print(f"[bold]Repo[/bold]     : {self.repo_path}")
        console.print(f"[bold]Run ID[/bold]   : {self.run.run_id}")
        console.print()

    # ID: start_phase_v1
    # ID: 2a98b30c-0cbb-48fd-a40a-270913ab982c
    def start_phase(self, name: str) -> DevSyncPhase:
        """
        Start a new phase and return it.

        Args:
            name: Human-readable phase name

        Returns:
            The created phase (for convenience)
        """
        phase = DevSyncPhase(name=name)
        self.phases.append(phase)
        self.current_phase = phase
        return phase

    # ID: record_result_v1
    # ID: ff8c918d-9521-4e82-bac6-00b01ffa9462
    def record_result(
        self,
        result: CommandResult,
        phase: DevSyncPhase | None = None,
    ) -> None:
        """
        Record a command result and emit structured activity log.

        Args:
            result: CommandResult from a command
            phase: Phase to add to (defaults to current_phase)
        """
        target_phase = phase or self.current_phase
        if target_phase is None:
            raise ValueError("No active phase. Call start_phase() first.")

        target_phase.results.append(result)

        # Log to activity stream
        status = "ok" if result.ok else "error"
        log_activity(
            self.run,
            event=f"command:{result.name}",
            status=status,
            message=f"Command {result.name} completed in {result.duration_sec:.2f}s",
            details={
                "command": result.name,
                "duration_sec": result.duration_sec,
                "data": result.data,
            },
        )

    # ID: print_phases_v1
    # ID: d4f9fb26-e073-4a28-a661-8431078967dc
    def print_phases(self) -> None:
        """Render all phases with their results in a table format."""
        if not self.phases:
            console.print("[italic]No phases recorded.[/italic]")
            return

        for phase in self.phases:
            # Phase header
            phase_status = "✓" if phase.ok else "✗"
            phase_color = "green" if phase.ok else "red"
            console.print(
                f"[bold {phase_color}]{phase_status}[/bold {phase_color}] "
                f"[bold]Phase: {phase.name}[/bold] "
                f"({phase.total_duration:.2f}s)"
            )

            # Results table for this phase
            if phase.results:
                table = Table(
                    show_header=True, header_style="bold", box=None, pad_edge=False
                )
                table.add_column("  Command", style="cyan", min_width=20)
                table.add_column("Time", justify="right", min_width=8)
                table.add_column("Status", min_width=6)
                table.add_column("Details", min_width=20)

                for result in phase.results:
                    # Status indicator
                    if result.ok:
                        status_text = Text("✓", style="green")
                    else:
                        status_text = Text("✗", style="red")

                    # Extract key detail for display
                    details = self._format_details(result)

                    table.add_row(
                        result.name,
                        f"{result.duration_sec:.2f}s",
                        status_text,
                        details,
                    )

                console.print(table)

            console.print()

    # ID: format_details_v1
    def _format_details(self, result: CommandResult) -> str:
        """
        Extract human-readable summary from result.data.

        Returns a concise string highlighting the key outcome.
        """
        if not result.ok and "error" in result.data:
            error_msg = result.data["error"][:40]
            return f"Error: {error_msg}"

        # Command-specific formatting
        if result.name == "fix.ids":
            count = result.data.get("ids_assigned", 0)
            return f"{count} IDs assigned"

        elif result.name == "fix.headers":
            violations = result.data.get("violations_found", 0)
            if violations == 0:
                return "All compliant"
            fixed = result.data.get("fixed_count", 0)
            return f"{fixed}/{violations} fixed"

        elif result.name in ["fix.docstrings", "fix.code-style", "fix.vector-sync"]:
            # Commands that just complete - don't show truncated output
            return "Completed"

        elif result.name == "check.lint":
            # Lint check - show if passed or had issues
            return "Passed" if result.ok else "Issues found"

        elif result.name in [
            "manage.sync-knowledge",
            "run.vectorize",
            "manage.define-symbols",
        ]:
            # DB sync commands - show completion without log noise
            return "Completed"

        elif result.name == "inspect.duplicates":
            # Analysis command
            return "Analyzed"

        elif "count" in result.data:
            # Generic count-based summary
            return f"{result.data['count']} processed"

        elif "output" in result.data:
            # CLI wrapper - just show "Completed" instead of truncated logs
            return "Completed"

        elif "success" in result.data:
            return "Completed" if result.data["success"] else "Failed"

        else:
            # Fallback
            return "Completed"

    # ID: print_summary_v1
    # ID: 232e679a-071f-4d1f-b131-dfad3352cfd1
    def print_summary(self) -> None:
        """Print final summary with phase breakdown and overall status."""
        if not self.phases:
            console.print("[bold]Summary[/bold]")
            console.print("  No phases executed.")
            console.rule()
            return

        # Count stats
        total_commands = sum(len(p.results) for p in self.phases)
        successful_commands = sum(
            sum(1 for r in p.results if r.ok) for p in self.phases
        )
        failed_commands = total_commands - successful_commands
        total_duration = sum(p.total_duration for p in self.phases)

        # Phase breakdown
        successful_phases = sum(1 for p in self.phases if p.ok)
        failed_phases = len(self.phases) - successful_phases

        # Overall status
        all_ok = all(p.ok for p in self.phases)

        console.print("[bold]Summary[/bold]")
        console.print(f"  Total phases   : {len(self.phases)}")
        console.print(f"  Successful     : {successful_phases}")
        if failed_phases > 0:
            console.print(f"  [red]Failed[/red]        : {failed_phases}")
        console.print()
        console.print(f"  Total commands : {total_commands}")
        console.print(f"  Successful     : {successful_commands}")
        if failed_commands > 0:
            console.print(f"  [red]Failed[/red]        : {failed_commands}")
        console.print()
        console.print(f"  Total duration : {total_duration:.2f}s")
        console.print()

        # Overall result
        if all_ok:
            console.print(
                "[bold green]✓ All phases completed successfully[/bold green]"
            )
        else:
            console.print("[bold red]✗ Some phases failed[/bold red]")
            # Show failed commands
            failed = [
                (p.name, r.name) for p in self.phases for r in p.results if not r.ok
            ]
            if failed:
                console.print("\n  Failed commands:")
                for phase_name, cmd_name in failed:
                    console.print(f"    - {phase_name} → {cmd_name}")

        console.print()
        console.rule()
