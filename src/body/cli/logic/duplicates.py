# src/body/cli/logic/duplicates.py

"""
Implements the dedicated 'inspect duplicates' command.

Refactored: Exposes async entry point for orchestrators.

Key behavior:
- Loads the AuditorContext knowledge graph (DB SSOT)
- Ensures QdrantService is available on the AuditorContext
- Runs DuplicationCheck (which reads qdrant_service from the context)
"""

from __future__ import annotations

import traceback
from pathlib import Path

import networkx as nx

from mind.governance.audit_context import AuditorContext
from mind.governance.check_registry import get_check
from shared.context import CoreContext
from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.logger import getLogger
from shared.models import AuditFinding


logger = getLogger(__name__)


def _group_findings(findings: list[AuditFinding]) -> list[list[AuditFinding]]:
    """Groups pairwise duplicate findings into clusters."""
    graph = nx.Graph()
    finding_map: dict[tuple[str, str], AuditFinding] = {}

    for finding in findings:
        ctx = finding.context or {}
        symbol1 = ctx.get("symbol_a")
        symbol2 = ctx.get("symbol_b")
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
                key=lambda f: float((f.context or {}).get("similarity", 0)),
                reverse=True,
            )
            grouped_findings.append(cluster_findings)

    return grouped_findings


# ID: 00ec62c1-ef50-4f17-aec6-460fe26a47d5
async def inspect_duplicates_async(context: CoreContext, threshold: float) -> None:
    """
    The core async logic for running only the duplication check.
    """
    if context is None:
        logger.error("Context not initialized for inspect duplicates")
        raise ValueError("Context not initialized for inspect duplicates")

    logger.info("Running semantic duplication check with threshold: %s...", threshold)

    try:
        from shared.config import settings

        repo_path = (
            getattr(getattr(context, "git_service", None), "repo_path", None)
            or settings.REPO_PATH
        )
        repo_root = Path(repo_path).resolve()

        if not repo_root.exists():
            raise FileNotFoundError(f"Repository path does not exist: {repo_root}")

        auditor_context = AuditorContext(repo_root)
        await auditor_context.load_knowledge_graph()

        # Resolve Qdrant service from CoreContext (preferred) or registry fallback
        qdrant_service: QdrantService | None = getattr(context, "qdrant_service", None)
        if qdrant_service is None:
            registry = getattr(context, "registry", None)
            if registry is not None:
                try:
                    qdrant_service = await registry.get_qdrant_service()
                    context.qdrant_service = qdrant_service
                except Exception as exc:
                    logger.warning("Could not initialize Qdrant service: %s", exc)
                    qdrant_service = None

        if qdrant_service is None:
            logger.error(
                "Qdrant service unavailable; cannot run duplication check. "
                "Ensure service is configured in context or registry."
            )
            return

        # Attach Qdrant service to auditor context
        auditor_context.qdrant_service = qdrant_service

        # Dynamic check lookup
        DuplicationCheck = get_check("DuplicationCheck")
        check = DuplicationCheck(auditor_context)

        findings = await check.execute(threshold=threshold)

        if not findings:
            logger.info("No significant duplicates found (threshold=%s).", threshold)
            return

        logger.info(
            "Found %s pairwise duplication finding(s) (threshold=%s).",
            len(findings),
            threshold,
        )

        # Group findings into clusters
        grouped = _group_findings(findings)
        logger.info("Grouped into %s cluster(s):", len(grouped))

        for idx, cluster_findings in enumerate(grouped, start=1):
            logger.info("Cluster %s:", idx)
            for finding in cluster_findings:
                ctx = finding.context or {}
                logger.info(
                    "  - %s <-> %s (similarity: %s)",
                    ctx.get("symbol_a", "???"),
                    ctx.get("symbol_b", "???"),
                    ctx.get("similarity", "???"),
                )

    except Exception as exc:
        logger.error("Duplication check failed: %s", exc)
        traceback.print_exc()
        raise
