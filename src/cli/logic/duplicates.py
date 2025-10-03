# src/cli/logic/duplicates.py
"""
Implements the dedicated 'inspect duplicates' command, providing a focused tool
to run only the semantic duplication check with clustering.
"""
from __future__ import annotations

import asyncio
from typing import List

import networkx as nx
import typer
from rich.console import Console
from rich.table import Table

from features.governance.audit_context import AuditorContext
from features.governance.checks.duplication_check import DuplicationCheck
from shared.context import CoreContext
from shared.models import AuditFinding

console = Console()


def _group_findings(findings: list[AuditFinding]) -> List[List[AuditFinding]]:
    """Groups individual finding pairs into clusters of related duplicates."""
    graph = nx.Graph()
    for finding in findings:
        # Extract the two symbols from the message
        parts = finding.message.split("'")
        if len(parts) >= 4:
            symbol1 = parts[1]
            symbol2 = parts[3]
            graph.add_edge(symbol1, symbol2, finding=finding)

    # Find connected components (these are our clusters)
    clusters = list(nx.connected_components(graph))

    # Map nodes back to findings
    finding_map = {
        (frozenset([p.message.split("'")[1], p.message.split("'")[3]])): p
        for p in findings
    }

    grouped_findings = []
    for cluster in clusters:
        cluster_findings = []
        # Create all pairs within the cluster to find the original findings
        edges = nx.Graph()
        edges.add_nodes_from(cluster)
        edges.add_edges_from(nx.complete_graph(cluster).edges())

        for u, v in edges.edges():
            pair = frozenset([u, v])
            if pair in finding_map:
                cluster_findings.append(finding_map[pair])

        if cluster_findings:
            # Sort by similarity score, descending
            cluster_findings.sort(
                key=lambda f: float(f.message.split(":")[-1].strip()[:-1]),
                reverse=True,
            )
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
        # All findings in a cluster share the same symbols, just different pairings
        all_symbols_in_cluster = set()
        for f in cluster:
            parts = f.message.split("'")
            all_symbols_in_cluster.add(parts[1])
            all_symbols_in_cluster.add(parts[3])

        title = f"Cluster #{i} ({len(all_symbols_in_cluster)} related symbols)"
        table = Table(show_header=True, header_style="bold magenta", title=title)
        table.add_column("Symbol 1", style="cyan")
        table.add_column("Symbol 2", style="cyan")
        table.add_column("Similarity", style="yellow")

        for finding in cluster:
            parts = finding.message.split("'")
            symbol1 = parts[1]
            symbol2 = parts[3]
            similarity = finding.message.split(":")[-1].strip()
            table.add_row(symbol1, symbol2, similarity)

        console.print(table)


# ID: 1a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d
def inspect_duplicates(context: CoreContext, threshold: float):
    """Runs only the semantic duplication check and reports the findings."""
    asyncio.run(_async_inspect_duplicates(context, threshold))
