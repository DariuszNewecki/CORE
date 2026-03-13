# src/will/workflows/dev_sync_reporter.py
"""
DevSyncReporter - User-facing reporting for dev-sync workflow.

Follows the same pattern as AuditRunReporter but for development synchronization.
Displays command results in a clean, structured format with phases and summary.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
from dataclasses import dataclass, field

from rich.console import Console
from rich.table import Table
from rich.text import Text

from shared.action_types import ActionResult
from shared.activity_logging import ActivityRun, log_activity
from shared.cli_types import CommandResult, _WorkflowResultsMixin


console = Console(log_time=False)
ResultLike = CommandResult | ActionResult


def _get_result_name(result: ResultLike) -> str:
    """
    Return a stable display name for a result.

    - For CommandResult -> use .name
    - For ActionResult  -> use .action_id
    """
    name = getattr(result, "name", None)
    if name:
        return name
    action_id = getattr(result, "action_id", None)
    if action_id:
        return action_id
    return "<unknown>"


@dataclass
# ID: 68fdbdaf-93b9-493a-8a0c-e4463422066c
class DevSyncPhase(_WorkflowResultsMixin):
    """Represents a logical phase in the dev-sync workflow."""

    name: str
    "Human-readable phase name (e.g., 'Fixers', 'Database Sync')"
    results: list[ResultLike] = field(default_factory=list)
    "Commands executed in this phase"


@dataclass
# ID: 482f7ae6-f304-4f78-b6e2-1037a6b47973
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

    # ID: cd9c52a2-7f56-4889-b27a-6ec7c92d27ca
    def print_header(self) -> None:
        """Print workflow header with run metadata."""
        console.rule("[bold]CORE Dev Sync Workflow[/bold]")
        logger.info("[bold]Workflow[/bold] : dev.sync")
        logger.info("[bold]Repo[/bold]     : %s", self.repo_path)
        logger.info("[bold]Run ID[/bold]   : %s", self.run.run_id)
        logger.info()

    # ID: f61b6aa4-0480-4cb9-98d8-368384893179
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

    # ID: 3e6a39a0-a178-4b02-b6e5-1e1158c29d2e
    def record_result(
        self, result: ResultLike, phase: DevSyncPhase | None = None
    ) -> None:
        """
        Record a command result and emit structured activity log.

        Args:
            result: CommandResult or ActionResult from a command
            phase: Phase to add to (defaults to current_phase)
        """
        target_phase = phase or self.current_phase
        if target_phase is None:
            raise ValueError("No active phase. Call start_phase() first.")
        target_phase.results.append(result)
        status = "ok" if result.ok else "error"
        name = _get_result_name(result)
        log_activity(
            self.run,
            event=f"command:{name}",
            status=status,
            message=f"Command {name} completed in {result.duration_sec:.2f}s",
            details={
                "command": name,
                "action_id": getattr(result, "action_id", None),
                "duration_sec": result.duration_sec,
                "data": result.data,
            },
        )

    # ID: d941566e-8815-485b-9eb5-81abf463bc62
    def print_phases(self) -> None:
        """Render all phases with their results in a table format."""
        if not self.phases:
            logger.info("[italic]No phases recorded.[/italic]")
            return
        for phase in self.phases:
            phase_status = "✓" if phase.ok else "✗"
            phase_color = "green" if phase.ok else "red"
            logger.info(
                "[bold %s]%s[/bold %s] [bold]Phase: %s[/bold] (%ss)",
                phase_color,
                phase_status,
                phase_color,
                phase.name,
                phase.total_duration,
            )
            if phase.results:
                table = Table(
                    show_header=True, header_style="bold", box=None, pad_edge=False
                )
                table.add_column("  Command", style="cyan", min_width=20)
                table.add_column("Time", justify="right", min_width=8)
                table.add_column("Status", min_width=6)
                table.add_column("Details", min_width=20)
                for result in phase.results:
                    if result.ok:
                        status_text = Text("✓", style="green")
                    else:
                        status_text = Text("✗", style="red")
                    details = self._format_details(result)
                    name = _get_result_name(result)
                    table.add_row(
                        name, f"{result.duration_sec:.2f}s", status_text, details
                    )
                logger.info(table)
            logger.info()

    def _format_details(self, result: ResultLike) -> str:
        """
        Extract human-readable summary from result.data.

        Returns a concise string highlighting the key outcome.
        """
        if not result.ok and "error" in result.data:
            error_msg = result.data["error"][:40]
            return f"Error: {error_msg}"
        name = _get_result_name(result)
        if name == "fix.ids":
            count = result.data.get("ids_assigned", 0)
            return f"{count} IDs assigned"
        elif name == "fix.headers":
            violations = result.data.get("violations_found", 0)
            fixed = result.data.get("fixed_count", 0)
            if result.data.get("dry_run", False):
                return f"{violations} violations (dry-run)"
            return f"{fixed}/{violations} header violations fixed"
        elif name == "fix.code-style":
            if result.ok:
                return "Formatted"
            return "Formatting failed"
        elif name == "fix.docstrings":
            fixed = result.data.get("fixed", 0)
            missing = result.data.get("missing", 0)
            if fixed or missing:
                return f"Fixed {fixed}, missing {missing}"
            return "Completed"
        elif name == "fix.vector-sync":
            if result.ok:
                return "Sync completed"
            return "Sync issues detected"
        elif name == "check.lint":
            return "Passed" if result.ok else "Issues found"
        elif name in [
            "manage.sync-knowledge",
            "run.vectorize",
            "manage.define-symbols",
        ]:
            return "Completed"
        elif name == "inspect.duplicates":
            return "Analyzed"
        elif "count" in result.data:
            return f"{result.data['count']} processed"
        elif "output" in result.data:
            return "Completed"
        elif "success" in result.data:
            return "Completed" if result.data["success"] else "Failed"
        else:
            return "Completed"

    # ID: 054bdea4-a6ec-442c-8724-d5f6fae0cc43
    def print_summary(self) -> None:
        """Print final summary with phase breakdown and overall status."""
        if not self.phases:
            logger.info("[bold]Summary[/bold]")
            logger.info("  No phases executed.")
            console.rule()
            return
        total_commands = sum(len(p.results) for p in self.phases)
        successful_commands = sum(
            sum(1 for r in p.results if r.ok) for p in self.phases
        )
        failed_commands = total_commands - successful_commands
        total_duration = sum(p.total_duration for p in self.phases)
        successful_phases = sum(1 for p in self.phases if p.ok)
        failed_phases = len(self.phases) - successful_phases
        all_ok = all(p.ok for p in self.phases)
        logger.info("[bold]Summary[/bold]")
        logger.info("  Total phases   : %s", len(self.phases))
        logger.info("  Successful     : %s", successful_phases)
        if failed_phases > 0:
            logger.info("  [red]Failed[/red]        : %s", failed_phases)
        logger.info()
        logger.info("  Total commands : %s", total_commands)
        logger.info("  Successful     : %s", successful_commands)
        if failed_commands > 0:
            logger.info("  [red]Failed[/red]        : %s", failed_commands)
        logger.info()
        logger.info("  Total duration : %ss", total_duration)
        logger.info()
        if all_ok:
            logger.info("[bold green]✓ All phases completed successfully[/bold green]")
        else:
            logger.info("[bold red]✗ Some phases failed[/bold red]")
            failed = [
                (p.name, _get_result_name(r))
                for p in self.phases
                for r in p.results
                if not r.ok
            ]
            if failed:
                logger.info("\n  Failed commands:")
                for phase_name, cmd_name in failed:
                    logger.info("    - %s → %s", phase_name, cmd_name)
        logger.info()
        console.rule()
