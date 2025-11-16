# src/body/cli/logic/duplicates.py
"""
Implements the dedicated 'inspect duplicates' command, providing a focused tool
to run only the semantic duplication check with clustering.
"""

from __future__ import annotations

import asyncio

import networkx as nx
import typer
from mind.governance.audit_context import AuditorContext
from mind.governance.checks.duplication_check import DuplicationCheck
from rich.console import Console
from rich.table import Table
from shared.context import CoreContext
from shared.models import AuditFinding

console = Console()


def _group_findings(findings: list[AuditFinding]) -> list[list[AuditFinding]]:
    """Groups individual finding pairs into clusters of related duplicates."""
    graph = nx.Graph()
    finding_map = {}

    for finding in findings:
        symbol1 = finding.context.get("symbol_a")
        symbol2 = finding.context.get("symbol_b")
        if symbol1 and symbol2:
            graph.add_edge(symbol1, symbol2)
            finding_map[tuple(sorted((symbol1, symbol2)))] = finding

    clusters = list(nx.connected_components(graph))
    grouped_findings = []

    for cluster in clusters:
        cluster_findings = []
        for i, node1 in enumerate(list(cluster)):
            for node2 in list(cluster)[i + 1 :]:
                key = tuple(sorted((node1, node2)))
                if key in finding_map:
                    cluster_findings.append(finding_map[key])

        if cluster_findings:
            # --- THIS IS THE FIX ---
            # The sorting key now correctly and safely reads the similarity score
            # from the finding's 'context' dictionary, preventing the ValueError.
            cluster_findings.sort(
                key=lambda f: float(f.context.get("similarity", 0)), reverse=True
            )
            # --- END OF FIX ---
            grouped_findings.append(cluster_findings)

    return grouped_findings


async def _async_inspect_duplicates(context: CoreContext, threshold: float):
    """The core async logic for running only the duplication check."""
    if context is None:
        console.print(
            "[bold red]Error: Context not initialized for inspect duplicates[/bold red]"
        )
        raise typer.Exit(code=1)

    console.print(
        f"[bold cyan]🚀 Running semantic duplication check with threshold: {threshold}...[/bold cyan]"
    )

    auditor_context = AuditorContext(context.git_service.repo_path)
    await auditor_context.load_knowledge_graph()
    duplication_check = DuplicationCheck(auditor_context)

    findings: list[AuditFinding] = await duplication_check.execute(threshold=threshold)

    if not findings:
        console.print("[bold green]✅ No semantic duplicates found.[/bold green]")
        return

    grouped_findings = _group_findings(findings)

    console.print(
        f"\n[bold yellow]Found {len(findings)} duplicate pairs, forming {len(grouped_findings)} cluster(s):[/bold yellow]"
    )

    for i, cluster in enumerate(grouped_findings, 1):
        all_symbols_in_cluster = set()
        for f in cluster:
            all_symbols_in_cluster.add(f.context["symbol_a"])
            all_symbols_in_cluster.add(f.context["symbol_b"])

        title = f"Cluster #{i} ({len(all_symbols_in_cluster)} related symbols)"
        table = Table(show_header=True, header_style="bold magenta", title=title)
        table.add_column("Symbol 1", style="cyan")
        table.add_column("Symbol 2", style="cyan")
        table.add_column("Similarity", style="yellow")

        for finding in cluster:
            table.add_row(
                finding.context["symbol_a"],
                finding.context["symbol_b"],
                finding.context["similarity"],
            )

        console.print(table)


# ID: 1a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d
def inspect_duplicates(context: CoreContext, threshold: float):
    """Runs only the semantic duplication check and reports the findings."""
    asyncio.run(_async_inspect_duplicates(context, threshold))
