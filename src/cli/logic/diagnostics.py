# src/cli/logic/diagnostics.py
"""
Implements deep diagnostic checks for system integrity and constitutional alignment.
"""
from __future__ import annotations

import asyncio
import json

import jsonschema
import typer
import yaml
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from ruamel.yaml import YAML

from features.governance.audit_context import AuditorContext
from features.governance.checks.domain_placement import DomainPlacementCheck
from features.governance.checks.legacy_tag_check import LegacyTagCheck
from features.governance.policy_coverage_service import PolicyCoverageService
from features.introspection.audit_unassigned_capabilities import get_unassigned_symbols
from features.introspection.graph_analysis_service import find_semantic_clusters
from shared.config import settings
from shared.models import AuditSeverity
from shared.utils.constitutional_parser import get_all_constitutional_paths

console = Console()
yaml_loader = YAML(typ="safe")
diagnostics_app = typer.Typer(help="Deep diagnostic and integrity checks.")


async def _async_find_clusters(n_clusters: int):
    """Async helper that contains the core logic for the command."""
    console.print(
        f"🚀 Finding semantic clusters with [bold cyan]n_clusters={n_clusters}[/bold cyan]..."
    )
    clusters = await find_semantic_clusters(n_clusters=n_clusters)

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
# ID: 1a9f1430-801c-42e7-9d7a-11586a117711
def find_clusters_command_sync(
    n_clusters: int = typer.Option(
        25, "--n-clusters", "-n", help="The number of clusters to find."
    )
):
    """Synchronous Typer wrapper for the async clustering logic."""
    asyncio.run(_async_find_clusters(n_clusters))


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
# ID: f4d5a5e3-1b9c-4e8a-9f7b-6c0d2e1a3b4c
def cli_tree():
    """Builds and displays the CLI command tree."""
    from cli.admin_cli import app as main_app

    console.print("[bold cyan]🚀 Building CLI Command Tree...[/bold cyan]")
    tree = Tree(
        "[bold magenta]🏛️ CORE Admin CLI Commands[/bold magenta]",
        guide_style="bold bright_blue",
    )
    _add_cli_nodes(tree, main_app)
    console.print(tree)


@diagnostics_app.command(
    "policy-coverage", help="Audits the constitution for policy coverage and integrity."
)
# ID: 74d7e7fd-1f68-4c4c-9dfb-285d1d7ee853
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
    console.print(f"Policies Seen: {report.summary['policies_seen']}")
    console.print(f"Rules Found: {report.summary['rules_found']}")
    console.print(f"Uncovered Rules: {report.summary['uncovered_rules']}")

    if report.summary["uncovered_rules"] > 0:
        table = Table(title="Uncovered Policy Rules")
        table.add_column("Policy", style="cyan")
        table.add_column("Rule ID", style="magenta")
        table.add_column("Enforcement", style="yellow")
        for record in report.records:
            if not record["covered"]:
                table.add_row(
                    record["policy_id"], record["rule_id"], record["enforcement"]
                )
        console.print(table)

    if report.exit_code != 0:
        console.print(
            f"\n[bold red]❌ Audit Failed with exit code: {report.exit_code}[/bold red]"
        )
        raise typer.Exit(code=report.exit_code)
    else:
        console.print(
            "\n[bold green]✅ All active policies are well-formed and covered.[/bold green]"
        )


@diagnostics_app.command(
    "debug-meta", help="Prints the auditor's view of all required constitutional files."
)
# ID: c4dba9d9-6c1a-4328-b473-2e3286e9d291
def debug_meta_paths():
    """A diagnostic tool to debug the constitutional file parser."""
    console.print(
        "[bold yellow]--- Auditor's Interpretation of meta.yaml ---[/bold yellow]"
    )
    intent_dir = settings.REPO_PATH / ".intent"
    required_paths = get_all_constitutional_paths(settings._meta_config, intent_dir)

    for path in sorted(list(required_paths)):
        console.print(path)


@diagnostics_app.command(
    "unassigned-symbols", help="Finds symbols without a universal # ID tag."
)
# ID: 41fdbad2-2bc4-4a4d-85c8-5f30461a4af0
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
# ID: a85348ac-fe9e-49d5-8b11-3a105a57a7e3
def manifest_hygiene():
    context = AuditorContext(settings.REPO_PATH)
    check = DomainPlacementCheck(context)
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
# ID: 58a9d61e-9899-4a10-bee2-c5473b3a91ba
def cli_registry():
    meta_content = (settings.REPO_PATH / ".intent" / "meta.yaml").read_text("utf-8")
    meta = yaml.safe_load(meta_content) or {}
    knowledge = meta.get("mind", {}).get("knowledge", {})
    schemas = meta.get("charter", {}).get("schemas", {})
    registry_rel = knowledge.get("cli_registry", "mind/knowledge/cli_registry.yaml")
    schema_rel = schemas.get(
        "cli_registry_schema", "charter/schemas/cli_registry_schema.json"
    )
    registry_path = (settings.REPO_PATH / registry_rel).resolve()
    schema_path = (settings.REPO_PATH / schema_rel).resolve()
    if not registry_path.exists():
        typer.secho(
            f"ERROR: CLI registry not found: {registry_path}",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
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
# ID: 2992fdb2-9b35-478d-a8df-28f23a7d605b
def check_legacy_tags():
    """Runs only the LegacyTagCheck to find obsolete capability tags."""

    async def _async_check_legacy_tags():
        console.print(
            "[bold cyan]🚀 Running standalone legacy tag check...[/bold cyan]"
        )
        context = AuditorContext(settings.REPO_PATH)
        await context.load_knowledge_graph()
        check = LegacyTagCheck(context)
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

        # --- THIS IS THE FIX ---
        # The table was being created but never printed.
        console.print(table)
        # --- END OF FIX ---

        raise typer.Exit(code=1)

    asyncio.run(_async_check_legacy_tags())
