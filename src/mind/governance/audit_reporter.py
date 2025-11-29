# src/mind/governance/audit_reporter.py
"""
AuditRunReporter: structured reporting for `core-admin check audit`.

Responsibilities:
- Print a clear run header
- Record and display phases (e.g. knowledge graph build)
- Record and display per-check results in a table
- Print a summary with key offenders and suggested fix commands
- Emit structured activity events via ActivityRun/log_activity
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from rich.console import Console
from rich.table import Table
from rich.text import Text
from shared.activity_logging import ActivityRun, log_activity
from shared.models import AuditSeverity

from mind.governance.audit_types import AuditCheckResult

console = Console()


@dataclass
# ID: 130b3778-81fa-4f45-b08a-ec7be01cb664
class AuditPhase:
    name: str
    duration_sec: float | None = None
    details: dict | None = None


@dataclass
# ID: 7e587f02-70d1-413b-8d32-884614e42670
class AuditRunReporter:
    """
    Coordinates user-facing reporting for a single audit run.

    Typical usage (inside the audit runner):

        reporter = AuditRunReporter(run, repo_path=..., total_checks=len(checks))
        reporter.print_header()

        # Phase 1: knowledge graph
        reporter.record_phase("Knowledge graph", duration_sec=2.65, details={"symbols": 1464})

        # For each check:
        result = AuditCheckResult.from_raw(check_cls, findings, duration_sec)
        reporter.record_check_result(result)

        # Finally:
        reporter.print_phases()
        reporter.print_checks_table()
        reporter.print_summary()
    """

    run: ActivityRun
    repo_path: str
    total_checks: int
    phases: list[AuditPhase] = field(default_factory=list)
    check_results: list[AuditCheckResult] = field(default_factory=list)

    # ID: c3b86fe8-f82a-4af4-be0b-0aef027dcaf2
    def print_header(self) -> None:
        console.rule("[bold]CORE Audit Run[/bold]")
        console.print("[bold]Workflow[/bold] : check.audit")
        console.print(f"[bold]Repo[/bold]     : {self.repo_path}")
        console.print(f"[bold]Run ID[/bold]   : {self.run.run_id}")
        console.print("-")

    # ---------- Phases ----------

    # ID: 29238d29-d5d9-4518-b392-28b7651290df
    def record_phase(
        self,
        name: str,
        duration_sec: float | None = None,
        details: dict | None = None,
    ) -> None:
        """Record a high-level audit phase (e.g. knowledge graph build)."""
        self.phases.append(
            AuditPhase(name=name, duration_sec=duration_sec, details=details)
        )

    # ID: ca1e280d-f07d-493c-a43d-57f0271c02b2
    def print_phases(self) -> None:
        """Render recorded phases to the console."""
        if not self.phases:
            return

        for phase in self.phases:
            console.print(f"[bold][Phase][/bold] {phase.name}")
            if phase.details:
                for key, value in phase.details.items():
                    console.print(f"  • {key}: {value}")
            if phase.duration_sec is not None:
                console.print(f"  • Duration: {phase.duration_sec:.2f}s")
            console.print()

    # ---------- Checks ----------

    # ID: 93d0968b-c2b9-4deb-a3ad-d6925bf49e33
    def record_check_result(
        self,
        result: AuditCheckResult,
        check_cls: type | None = None,
    ) -> None:
        """
        Record a normalized check result and emit a structured activity event.

        If check_cls is provided, the event name will include the class name.
        """
        self.check_results.append(result)

        event_name = "check"
        if check_cls is not None:
            event_name = f"check:{check_cls.__name__}"

        status = "ok" if result.findings_count == 0 else "warning"

        log_activity(
            self.run,
            event=event_name,
            status=status,
            message=(
                f"Check {result.name} completed with "
                f"{result.findings_count} findings in {result.duration_sec:.2f}s"
            ),
            details={
                "check_name": result.name,
                "category": result.category,
                "duration_sec": result.duration_sec,
                "findings_count": result.findings_count,
                "max_severity": (
                    result.max_severity.name if result.max_severity else None
                ),
            },
        )

    # ID: de543ad4-2e18-431f-9730-2af1917e753c
    def print_checks_table(self) -> None:
        """Render a table of all check results."""
        if not self.check_results:
            console.print("[italic]No checks recorded.[/italic]")
            return

        table = Table(show_header=True, header_style="bold")
        table.add_column("CHECK", style="bold", min_width=26)
        table.add_column("CATEGORY", min_width=10)
        table.add_column("TIME", justify="right")
        table.add_column("FINDINGS", justify="right")
        table.add_column("STATUS", min_width=10)

        for result in self.check_results:
            if result.findings_count == 0:
                status_text = Text("OK")
            else:
                status_text = Text("WARN")
                status_text.stylize("yellow")

            table.add_row(
                result.name,
                result.category or "-",
                f"{result.duration_sec:.2f}s",
                str(result.findings_count),
                status_text,
            )

        console.print(
            f"[bold][Phase][/bold] Running checks ({self.total_checks} total)"
        )
        console.print(table)
        console.print()

    # ---------- Summary ----------

    # ID: f8c33425-418f-40e2-b059-811098ae0c1c
    def print_summary(self) -> None:
        """Render a summary block with counts and suggested next steps."""
        if not self.check_results:
            console.print("[bold]Summary[/bold]")
            console.print("  No checks were executed.")
            console.rule()
            return

        total = len(self.check_results)
        with_issues = [r for r in self.check_results if r.has_issues]
        findings_total = sum(r.findings_count for r in self.check_results)

        # Determine highest severity present (if any)
        severities: list[AuditSeverity] = []
        for r in self.check_results:
            if r.max_severity is not None:
                severities.append(r.max_severity)
        highest_severity = max(severities) if severities else None

        console.print("[bold][Summary][/bold]")
        console.print(f"  Total checks      : {total}")
        console.print(f"  Checks with issues: {len(with_issues)}")
        console.print(f"  Total findings    : {findings_total}")
        if highest_severity:
            console.print(f"  Highest severity  : {highest_severity.name}")
        console.print()

        offenders = sorted(with_issues, key=lambda r: r.findings_count, reverse=True)[
            :5
        ]
        if offenders:
            console.print("  Key offenders:")
            for r in offenders:
                console.print(f"    - {r.name}: {r.findings_count} findings")
            console.print()

        hints = _collect_fix_hints(offenders)
        if hints:
            console.print("  Suggested next steps:")
            for cmd in hints:
                console.print(f"    - Run: [bold]{cmd}[/bold]")
            console.print()

        console.rule()


def _collect_fix_hints(results: Iterable[AuditCheckResult]) -> list[str]:
    """Return a de-duplicated list of fix hints from check results."""
    seen: set[str] = set()
    hints: list[str] = []

    for r in results:
        if r.fix_hint and r.fix_hint not in seen:
            seen.add(r.fix_hint)
            hints.append(r.fix_hint)

    return hints
