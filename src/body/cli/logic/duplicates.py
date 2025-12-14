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
from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.logger import getLogger
from shared.models import AuditFinding


logger = getLogger(__name__)


def _group_findings(findings: list[AuditFinding]) -> list[list[AuditFinding]]:
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


# ID: 865b826f-4609-4816-abac-e7f8ea86f275
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

    # Inject qdrant_service into auditor_context so DuplicationCheck can access it
    auditor_context.qdrant_service = qdrant_service

    duplication_check = DuplicationCheck(context=auditor_context)
    findings: list[AuditFinding] = await duplication_check.execute(threshold=threshold)
    if not findings:
        logger.info("No semantic duplicates found.")
        return
    grouped_findings = _group_findings(findings)
    logger.info(
        "Found %s duplicate pairs, forming %s cluster(s)",
        len(findings),
        len(grouped_findings),
    )
    for i, cluster in enumerate(grouped_findings, 1):
        all_symbols_in_cluster = set()
        for f in cluster:
            all_symbols_in_cluster.add(f.context["symbol_a"])
            all_symbols_in_cluster.add(f.context["symbol_b"])
        logger.info("Cluster #%s (%s related symbols):", i, len(all_symbols_in_cluster))
        for finding in cluster:
            logger.info(
                "  %s <-> %s: %s",
                finding.context["symbol_a"],
                finding.context["symbol_b"],
                float(finding.context.get("similarity", 0)),
            )


# ID: fb272ce8-7a9f-4efc-81f5-3b2fdf642ba4
def inspect_duplicates(context: CoreContext, threshold: float = 0.8):
    """Runs only the semantic duplication check and reports the findings (CLI wrapper)."""
    asyncio.run(inspect_duplicates_async(context, threshold))
