# src/body/cli/resources/admin/self_check.py
# ID: 8aaa8328-3e1b-4217-9a1b-d1d270d6eaec

"""
CLI Self-Check Command — Phase 1 Capability Closure.

Thin CLI wrapper over audit_cli_registry() from command_sync_service.
Formats the audit report dict for human consumption via Rich,
or outputs raw JSON for scripting/CI.

Roadmap: Phase 1, Deliverable #3 (Command Self-Check Mode).

Constitutional Alignment:
- Pure READ/VALIDATE operation, no mutations
- No database dependency
- Deterministic output
- Exit code 1 on issues (CI-friendly)
"""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from shared.cli_utils import core_command
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


console = Console()


@app.command("self-check")
@command_meta(
    canonical_name="admin.self-check",
    behavior=CommandBehavior.VALIDATE,
    layer=CommandLayer.BODY,
    summary="Validate CLI command registration integrity",
)
@core_command(dangerous=False, requires_context=False)
# ID: f7a1b2c3-d4e5-6789-abcd-ef0123456789
def self_check_cmd(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show full command listing."
    ),
    output_json: bool = typer.Option(
        False, "--json", help="Output raw JSON report (for scripting/CI)."
    ),
) -> None:
    """
    Validate CLI command registration integrity.

    Checks:
    - Every registered command has a handler (callback)
    - @command_meta decorator coverage
    - No duplicate canonical names
    - Experimental command inventory

    Exit code 0 if healthy, 1 if issues found.

    Examples:
        core-admin admin self-check
        core-admin admin self-check --verbose
        core-admin admin self-check --json
    """
    from body.cli.admin_cli import app as main_app
    from body.maintenance.command_sync_service import audit_cli_registry

    report = audit_cli_registry(main_app)

    # JSON mode: dump and exit
    if output_json:
        console.print_json(json.dumps(report, default=str))
        if not report["is_healthy"]:
            raise typer.Exit(1)
        return

    # Human-readable mode
    console.print(
        "[bold cyan]🔍 CORE CLI Self-Check — Registry Integrity Audit[/bold cyan]\n"
    )

    total = report["total_commands"]
    console.print(f"  Total commands discovered:  [bold]{total}[/bold]")
    console.print(
        f"  With @command_meta:        [bold]{report['with_explicit_meta']}[/bold]"
        f"  ({report['meta_coverage_pct']}%)"
    )
    console.print(
        f"  Inferred metadata:         [bold]{report['with_inferred_meta']}[/bold]"
    )
    console.print(
        f"  Missing handlers:          [bold red]{len(report['missing_handlers'])}[/bold red]"
    )
    console.print(
        f"  Duplicate canonical names: [bold red]{len(report['duplicates'])}[/bold red]"
    )
    console.print(
        f"  Experimental commands:     [dim]{report['experimental_count']}[/dim]"
    )
    console.print()

    # Detail: missing handlers
    if report["missing_handlers"]:
        console.print("[bold red]❌ Commands with MISSING handlers:[/bold red]")
        for entry in report["missing_handlers"]:
            console.print(f"   • {entry['name']} (group: {entry['category']})")
        console.print()

    # Detail: duplicates
    if report["duplicates"]:
        console.print("[bold red]❌ Duplicate canonical names:[/bold red]")
        for dup in report["duplicates"]:
            console.print(
                f"   • '{dup['canonical_name']}' registered by: "
                f"{', '.join(dup['locations'])}"
            )
        console.print()

    # Detail: experimental
    if report["experimental"]:
        console.print("[yellow]🧪 Experimental commands (hidden from --help):[/yellow]")
        for entry in report["experimental"]:
            console.print(f"   • {entry['name']}")
        console.print()

    # Verbose: full command table
    if verbose:
        console.print("[bold]📋 Full Command Registry:[/bold]")
        table = Table(show_header=True, header_style="bold")
        table.add_column("#", justify="right", style="dim")
        table.add_column("Canonical Name", style="cyan")
        table.add_column("Meta", justify="center")
        table.add_column("Handler", justify="center")
        table.add_column("Exp", justify="center")
        table.add_column("Module")

        for i, cmd in enumerate(report["commands"], 1):
            meta_icon = "✅" if cmd.get("has_explicit_meta") else "❌"
            handler_icon = "✅" if cmd.get("has_callback") else "❌"
            exp_icon = "🧪" if cmd.get("experimental") else ""
            table.add_row(
                str(i),
                cmd.get("name", "—"),
                meta_icon,
                handler_icon,
                exp_icon,
                cmd.get("module", "—") or "—",
            )
        console.print(table)
        console.print()

    # Verdict
    if report["is_healthy"]:
        console.print(
            f"[bold green]✅ CLI Registry Integrity: PASS[/bold green]"
            f" — {total} commands, all clean."
        )
    else:
        console.print(
            f"[bold yellow]⚠️  CLI Registry Integrity:"
            f" {report['issue_count']} issue(s) found[/bold yellow]"
        )
        if not verbose:
            console.print("[dim]Run with --verbose for the full command listing.[/dim]")
        raise typer.Exit(1)
