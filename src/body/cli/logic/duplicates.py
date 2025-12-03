# src/body/cli/logic/duplicates.py
"""
Implements the dedicated 'inspect duplicates' command.

Refactored: Exposes async entry point for orchestrators.
"""

from __future__ import annotations

import asyncio

import networkx as nx
import typer
from mind.governance.audit_context import AuditorContext
from mind.governance.checks.duplication_check import DuplicationCheck
from rich.console import Console
from rich.table import Table
from services.clients.qdrant_client import (
    QdrantService,
)
from shared.context import CoreContext
from shared.models import AuditFinding

console = Console()


def _group_findings(findings: list[AuditFinding]) -> list[list[AuditFinding]]:
    # ... (omitted for brevity - keeping logic same as before) ...
    # Re-pasting entire function to be safe
    graph = nx.Graph()
    finding_map: dict[tuple[str, str], AuditFinding] = {}

    for finding in findings:
        symbol1 = finding.context.get("symbol_a")
        symbol2 = finding.context.get("symbol_b")
        if symbol1 and symbol2:
            graph.add_edge(symbol1, symbol2)
            finding_map[tuple(sorted((symbol1, symbol2)))] = finding

    clusters = list(nx.connected_components(graph))
    grouped_findings: list[list[AuditFinding]] = []

    for cluster in clusters:
        cluster_findings: list[AuditFinding] = []
        nodes = list(cluster)
        for i, node1 in enumerate(nodes):
            for node2 in nodes[i + 1 :]:
                key = tuple(sorted((node1, node2)))
                if key in finding_map:
                    cluster_findings.append(finding_map[key])

        if cluster_findings:
            cluster_findings.sort(
                key=lambda f: float(f.context.get("similarity", 0)), reverse=True
            )
            grouped_findings.append(cluster_findings)

    return grouped_findings


# RENAMED from _async_inspect_duplicates to inspect_duplicates_async and exported
# ID: b23abebe-85a7-4bd2-8bf3-37381edbab89
async def inspect_duplicates_async(context: CoreContext, threshold: float):
    """
    The core async logic for running only the duplication check.
    Exported for use by orchestrators like dev_sync.
    """
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

    qdrant_service: QdrantService | None = context.qdrant_service

    # JIT Injection logic (same as before)
    if not qdrant_service and context.registry:
        try:
            qdrant_service = await context.registry.get_qdrant_service()
            context.qdrant_service = qdrant_service
            if context.cognitive_service:
                context.cognitive_service._qdrant_service = qdrant_service
        except Exception as e:
            console.print(
                f"[yellow]Warning: Could not initialize Qdrant service: {e}[/yellow]"
            )

    if not qdrant_service and context.cognitive_service:
        qdrant_service = getattr(context.cognitive_service, "_qdrant_service", None)

    duplication_check = DuplicationCheck(
        context=auditor_context,
        qdrant_service=qdrant_service,
    )

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
                f"{float(finding.context.get('similarity', 0)):.3f}",
            )

        console.print(table)


# ID: 20870972-4c43-46c5-aa60-7079e9a99db8
def inspect_duplicates(context: CoreContext, threshold: float = 0.8):
    """Runs only the semantic duplication check and reports the findings (CLI wrapper)."""
    asyncio.run(inspect_duplicates_async(context, threshold))
