# src/body/cli/logic/duplicates.py
"""
Implements the dedicated 'inspect duplicates' command.

Refactored: Exposes async entry point for orchestrators.
"""

from __future__ import annotations

import asyncio

import networkx as nx

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.duplication_check import DuplicationCheck
from shared.context import CoreContext
from shared.infrastructure.clients.qdrant_client import (
    QdrantService,
)
from shared.logger import getLogger
from shared.models import AuditFinding


logger = getLogger(__name__)


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
        logger.error("Error: Context not initialized for inspect duplicates")
        raise ValueError("Context not initialized for inspect duplicates")

    logger.info("Running semantic duplication check with threshold: %s...", threshold)

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
            logger.warning("Warning: Could not initialize Qdrant service: %s", e)

    if not qdrant_service and context.cognitive_service:
        qdrant_service = getattr(context.cognitive_service, "_qdrant_service", None)

    duplication_check = DuplicationCheck(
        context=auditor_context,
        qdrant_service=qdrant_service,
    )

    findings: list[AuditFinding] = await duplication_check.execute(threshold=threshold)

    if not findings:
        logger.info("No semantic duplicates found.")
        return

    grouped_findings = _group_findings(findings)

    logger.info(
        f"Found {len(findings)} duplicate pairs, forming {len(grouped_findings)} cluster(s)"
    )

    for i, cluster in enumerate(grouped_findings, 1):
        all_symbols_in_cluster = set()
        for f in cluster:
            all_symbols_in_cluster.add(f.context["symbol_a"])
            all_symbols_in_cluster.add(f.context["symbol_b"])

        logger.info("Cluster #%s ({len(all_symbols_in_cluster)} related symbols):", i)
        for finding in cluster:
            logger.info(
                f"  {finding.context['symbol_a']} <-> {finding.context['symbol_b']}: "
                f"{float(finding.context.get('similarity', 0)):.3f}"
            )


# ID: 20870972-4c43-46c5-aa60-7079e9a99db8
def inspect_duplicates(context: CoreContext, threshold: float = 0.8):
    """Runs only the semantic duplication check and reports the findings (CLI wrapper)."""
    asyncio.run(inspect_duplicates_async(context, threshold))
