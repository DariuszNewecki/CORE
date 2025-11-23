# src/body/cli/logic/diagnostics.py
"""
Implements deep diagnostic checks for system integrity and constitutional alignment.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import jsonschema
import typer
import yaml
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from ruamel.yaml import YAML

from features.introspection.audit_unassigned_capabilities import get_unassigned_symbols
from features.introspection.graph_analysis_service import find_semantic_clusters
from mind.governance.checks.domain_placement import DomainPlacementCheck
from mind.governance.checks.legacy_tag_check import LegacyTagCheck
from mind.governance.policy_coverage_service import PolicyCoverageService
from shared.config import settings
from shared.context import CoreContext
from shared.models import AuditSeverity
from shared.utils.constitutional_parser import get_all_constitutional_paths

console = Console()
yaml_loader = YAML(typ="safe")
diagnostics_app = typer.Typer(help="Deep diagnostic and integrity checks.")


async def _async_find_clusters(context: CoreContext, n_clusters: int):
    """Async helper that contains the core logic for the command."""
    console.print(
        f"🚀 Finding semantic clusters with [bold cyan]n_clusters={n_clusters}[/bold cyan]..."
    )
    # The qdrant_service is passed in from the context.
    clusters = await find_semantic_clusters(
        qdrant_service=context.qdrant_service, n_clusters=n_clusters
    )

    if not clusters:
        console.print("⚠️  No clusters found.")
        return

    console.print(f"✅ Found {len(clusters)} clusters. Displaying all, sorted by size.")

    for i, cluster in enumerate(clusters):
        if not cluster:
            continue

        table = Table(
            title=f"Semantic Cluster #{i + 1} ({len(cluster)} symbols)",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Symbol Key", style="cyan", no_wrap=True)

        for symbol_key in sorted(cluster):
            table.add_row(symbol_key)

        console.print(table)


@diagnostics_app.command(
    "find-clusters",
    help="Finds and displays all semantic capability clusters, sorted by size.",
)
# ID: fb7f9a46-4053-4a2b-bbcb-b937ffa55909
def find_clusters_command_sync(
    ctx: typer.Context,
    n_clusters: int = typer.Option(
        25, "--n-clusters", "-n", help="The number of clusters to find."
    ),
):
    """Synchronous Typer wrapper for the async clustering logic."""
    core_context: CoreContext = ctx.obj
    asyncio.run(_async_find_clusters(core_context, n_clusters))


def _add_cli_nodes(tree_node: Tree, cli_app: typer.Typer):
    for cmd_info in sorted(cli_app.registered_commands, key=lambda c: c.name or ""):
        if not cmd_info.name:
            continue
        help_text = cmd_info.help.split("\n")[0] if cmd_info.help else ""
        tree_node.add(
            f"[bold yellow]⚡ {cmd_info.name}[/bold yellow] [dim]- {help_text}[/dim]"
        )
    for group_info in sorted(cli_app.registered_groups, key=lambda g: g.name or ""):
        if not group_info.name:
            continue
        help_text = (
            group_info.typer_instance.info.help.split("\n")[0]
            if group_info.typer_instance.info.help
            else ""
        )
        branch = tree_node.add(
            f"[cyan]📂 {group_info.name}[/cyan] [dim]- {help_text}[/dim]"
        )
        _add_cli_nodes(branch, group_info.typer_instance)


@diagnostics_app.command(
    "cli-tree", help="Displays a hierarchical tree view of all available CLI commands."
)
# ID: 30a6dcde-a174-48de-8f0f-327cbafec340
def cli_tree():
    """Builds and displays the CLI command tree."""
    from body.cli.admin_cli import app as main_app

    console.print("[bold cyan]🚀 Building CLI Command Tree...[/bold cyan]")
    tree = Tree(
        "[bold magenta]🏛️ CORE Admin CLI Commands[/bold magenta]",
        guide_style="bold bright_blue",
    )
    _add_cli_nodes(tree, main_app)
    console.print(tree)


def _print_policy_coverage_summary(summary: dict[str, Any]) -> None:
    """Print a compact summary of policy coverage metrics."""
    console.print()
    console.print(
        "[bold underline]Constitutional Policy Coverage Summary[/bold underline]"
    )

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")

    table.add_row("Policies Seen", str(summary.get("policies_seen", 0)))
    table.add_row("Rules Found", str(summary.get("rules_found", 0)))
    table.add_row("Rules (direct)", str(summary.get("rules_direct", 0)))
    table.add_row("Rules (bound)", str(summary.get("rules_bound", 0)))
    table.add_row("Rules (inferred)", str(summary.get("rules_inferred", 0)))
    table.add_row("Uncovered Rules (all)", str(summary.get("uncovered_rules", 0)))
    table.add_row(
        "Uncovered ERROR Rules",
        str(summary.get("uncovered_error_rules", 0)),
    )

    console.print(table)
    console.print()


def _print_policy_coverage_table(records: list[dict[str, Any]]) -> None:
    """Show all rules with their coverage type so gaps are visible."""
    if not records:
        console.print(
            "[yellow]No policy rules discovered; nothing to display.[/yellow]"
        )
        return

    console.print("[bold underline]Policy Rules Coverage[/bold underline]")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Policy", style="bold")
    table.add_column("Rule ID")
    table.add_column("Enforcement", justify="center")
    table.add_column("Coverage", justify="center")
    table.add_column("Covered?", justify="center")

    # Sort: uncovered first, then by policy, then by rule id
    sorted_records = sorted(
        records,
        key=lambda r: (
            not r.get("covered", False),
            r.get("policy_id", ""),
            r.get("rule_id", ""),
        ),
    )

    for rec in sorted_records:
        policy = rec.get("policy_id", "")
        rule_id = rec.get("rule_id", "")
        enforcement = rec.get("enforcement", "")
        coverage = rec.get("coverage", "none")
        covered = rec.get("covered", False)

        covered_str = "[green]Yes[/green]" if covered else "[red]No[/red]"
        table.add_row(policy, rule_id, enforcement, coverage, covered_str)

    console.print(table)
    console.print()


def _print_uncovered_policy_rules(records: list[dict[str, Any]]) -> None:
    """Legacy-style view: only show the rules that are not covered."""
    uncovered = [r for r in records if not r.get("covered", False)]
    if not uncovered:
        return

    console.print("[bold underline]Uncovered Policy Rules[/bold underline]")

    table = Table(show_header=True, header_style="bold red")
    table.add_column("Policy")
    table.add_column("Rule ID")
    table.add_column("Enforcement", justify="center")
    table.add_column("Coverage", justify="center")

    for rec in uncovered:
        table.add_row(
            rec.get("policy_id", ""),
            rec.get("rule_id", ""),
            rec.get("enforcement", ""),
            rec.get("coverage", "none"),
        )

    console.print(table)
    console.print()


@diagnostics_app.command(
    "policy-coverage", help="Audits the constitution for policy coverage and integrity."
)
# ID: 25d4e8f9-ae1e-424e-972d-2dcb74f918b7
def policy_coverage():
    """
    Runs a meta-audit on all .intent/charter/policies/ to ensure they are
    well-formed and covered by the governance model.
    """
    console.print(
        "[bold cyan]🚀 Running Constitutional Policy Coverage Audit...[/bold cyan]"
    )
    service = PolicyCoverageService()
    report = service.run()

    console.print(f"Report ID: [dim]{report.report_id}[/dim]")

    # Enhanced summary with coverage breakdown
    _print_policy_coverage_summary(report.summary)

    # Full coverage table (including coverage type)
    _print_policy_coverage_table(report.records)

    # Focused view on uncovered rules (if any)
    if report.summary.get("uncovered_rules", 0) > 0:
        _print_uncovered_policy_rules(report.records)

    if report.exit_code != 0:
        console.print(
            f"[bold red]❌ Policy coverage audit failed with exit code: {report.exit_code}[/bold red]"
        )
        raise typer.Exit(code=report.exit_code)

    console.print(
        "[bold green]✅ All active policies are backed by implemented or inferred checks.[/bold green]"
    )


@diagnostics_app.command(
    "debug-meta", help="Prints the auditor's view of all required constitutional files."
)
# ID: 993e903f-d239-44bf-95ec-1eb0422094cd
def debug_meta_paths():
    """A diagnostic tool that prints all file paths indexed in meta.yaml."""
    console.print(
        "[bold yellow]--- Auditor's Interpretation of meta.yaml ---[/bold yellow]"
    )
    required_paths = get_all_constitutional_paths(settings._meta_config, settings.MIND)
    for path in sorted(list(required_paths)):
        console.print(path)


@diagnostics_app.command(
    "unassigned-symbols", help="Finds symbols without a universal # ID tag."
)
# ID: 6e1b1104-fd07-4865-88bd-d376da96c0f4
def unassigned_symbols():
    unassigned = get_unassigned_symbols()
    if not unassigned:
        console.print(
            "[bold green]✅ Success! All governable symbols have an assigned ID tag.[/bold green]"
        )
        return
    console.print(
        f"\n[bold red]❌ Found {len(unassigned)} symbols with no assigned ID:[/bold red]"
    )
    table = Table(title="Untagged Symbols ('Orphaned Logic')")
    table.add_column("Symbol Key", style="cyan", no_wrap=True)
    table.add_column("File", style="yellow")
    table.add_column("Line", style="magenta")
    for symbol in sorted(unassigned, key=lambda s: s["key"]):
        table.add_row(symbol["key"], symbol["file"], str(symbol["line_number"]))
    console.print(table)
    console.print("\n[bold]Action Required:[/bold] Run 'knowledge sync' to assign IDs.")


@diagnostics_app.command(
    "manifest-hygiene",
    help="Checks for capabilities declared in the wrong domain manifest file.",
)
# ID: d90abaa5-8336-4f11-bd52-8d1088f037da
def manifest_hygiene(ctx: typer.Context):
    """Checks for misplaced capabilities in domain manifests."""
    core_context: CoreContext = ctx.obj
    check = DomainPlacementCheck(core_context.auditor_context)
    findings = check.execute()
    if not findings:
        console.print(
            "[bold green]✅ All capabilities correctly placed in domain manifests[/bold green]"
        )
        raise typer.Exit(code=0)
    errors = [f for f in findings if f.severity == AuditSeverity.ERROR]
    if errors:
        console.print(f"[bold red]🚨 {len(errors)} CRITICAL errors found:[/bold red]")
        for f in errors:
            console.print(f"  [red]{f}[/red]")
    if warnings := [f for f in findings if f.severity == AuditSeverity.WARNING]:
        console.print(f"[bold yellow]⚠️  {len(warnings)} warnings found:[/bold yellow]")
        for f in warnings:
            console.print(f"  [yellow]{f}[/yellow]")
    raise typer.Exit(code=1 if errors else 0)


@diagnostics_app.command(
    "cli-registry", help="Validates the CLI registry against its constitutional schema."
)
# ID: d0f4af61-2e34-4c98-989e-1b9dd9214e31
def cli_registry():
    meta_content = (settings.REPO_PATH / ".intent" / "meta.yaml").read_text("utf-8")
    meta = yaml.safe_load(meta_content) or {}
    # This logic might need updating if these paths change in your new meta.yaml
    knowledge = meta.get("mind", {}).get("knowledge", {})
    schemas = meta.get("charter", {}).get("schemas", {})
    registry_rel = knowledge.get("cli_registry", "mind/knowledge/cli_registry.yaml")
    schema_rel = schemas.get(
        "cli_registry_schema", "charter/schemas/cli_registry_schema.json"
    )

    registry_path = (settings.REPO_PATH / registry_rel).resolve()
    schema_path = (settings.REPO_PATH / schema_rel).resolve()

    # Gracefully handle missing legacy files
    if not registry_path.exists():
        typer.secho(
            "INFO: Legacy CLI registry not found (this is expected after SSOT migration).",
            fg=typer.colors.CYAN,
        )
        return

    if not schema_path.exists():
        typer.secho(
            f"ERROR: CLI registry schema not found: {schema_path}",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    registry_content = registry_path.read_text("utf-8")
    registry = yaml.safe_load(registry_content) or {}
    schema_content = schema_path.read_text(encoding="utf-8")
    schema = json.loads(schema_content)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(registry), key=lambda e: e.path)
    if errors:
        typer.secho(
            f"❌ CLI registry failed validation against {schema_rel}",
            err=True,
            fg=typer.colors.RED,
        )
        for idx, err in enumerate(errors, 1):
            loc = "/".join(map(str, err.path)) or "(root)"
            typer.secho(
                f"  {idx}. at {loc}: {err.message}", err=True, fg=typer.colors.RED
            )
        raise typer.Exit(1)
    typer.secho(f"✅ CLI registry is valid: {registry_rel}", fg=typer.colors.GREEN)


@diagnostics_app.command("legacy-tags", help="Scans the codebase for obsolete tags.")
# ID: de787795-39e8-414a-9ea7-bd3d4bf22ef6
def check_legacy_tags(ctx: typer.Context):
    """Runs only the LegacyTagCheck to find obsolete capability tags."""
    core_context: CoreContext = ctx.obj

    async def _async_check_legacy_tags():
        console.print(
            "[bold cyan]🚀 Running standalone legacy tag check...[/bold cyan]"
        )
        check = LegacyTagCheck(core_context.auditor_context)
        findings = check.execute()
        if not findings:
            console.print("[bold green]✅ Success! No legacy tags found.[/bold green]")
            return

        console.print(
            f"\n[bold red]❌ Found {len(findings)} instance(s) of legacy tags:[/bold red]"
        )
        table = Table(title="Obsolete Tag Violations")
        table.add_column("File Path", style="cyan", no_wrap=True)
        table.add_column("Line", style="magenta")
        table.add_column("Message", style="red")
        for finding in findings:
            table.add_row(finding.file_path, str(finding.line_number), finding.message)

        console.print(table)
        raise typer.Exit(code=1)

    asyncio.run(_async_check_legacy_tags())
