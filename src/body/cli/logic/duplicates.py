# src/body/cli/logic/duplicates.py

"""
Logic for the 'inspect duplicates' command.
Refactored to use the dynamic constitutional rule engine and provide
both AST and semantic code duplication analysis.
"""

from __future__ import annotations

import traceback

import networkx as nx

from mind.governance.audit_context import AuditorContext
from shared.context import CoreContext
from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.logger import getLogger
from shared.models import AuditFinding


logger = getLogger(__name__)


def _group_findings(findings: list[AuditFinding]) -> list[list[AuditFinding]]:
    """Groups pairwise duplicate findings into clusters using graph theory."""
    graph = nx.Graph()
    finding_map: dict[tuple[str, str], AuditFinding] = {}

    for finding in findings:
        ctx = finding.context or {}
        symbol1 = ctx.get("symbol_a")
        symbol2 = ctx.get("symbol_b")
        if symbol1 and symbol2:
            graph.add_edge(symbol1, symbol2)
            # Sort keys to ensure consistent mapping
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
            # Sort by similarity within the cluster
            cluster_findings.sort(
                key=lambda f: float((f.context or {}).get("similarity", 0)),
                reverse=True,
            )
            grouped_findings.append(cluster_findings)

    return grouped_findings


# ID: 00ec62c1-ef50-4f17-aec6-460fe26a47d5
async def inspect_duplicates_async(context: CoreContext, threshold: float) -> None:
    """
    The core async logic for running duplication analysis.
    Uses the constitutional rule engine to identify duplicates.
    """
    # CONSTITUTIONAL FIX: Local imports to break circular dependency
    from mind.governance.rule_executor import execute_rule
    from mind.governance.rule_extractor import extract_executable_rules

    if context is None:
        logger.error("Context not initialized for inspect duplicates")
        raise ValueError("Context not initialized for inspect duplicates")

    logger.info("🔍 Running duplication checks (threshold: %s)...", threshold)

    try:
        # 1. Initialize AuditorContext and load state
        repo_root = context.git_service.repo_path
        auditor_context = context.auditor_context or AuditorContext(repo_root)
        await auditor_context.load_knowledge_graph()

        # 2. Ensure Qdrant is available (required for semantic duplication)
        qdrant_service: QdrantService | None = context.qdrant_service
        if qdrant_service is None and context.registry:
            qdrant_service = await context.registry.get_qdrant_service()
            context.qdrant_service = qdrant_service

        if qdrant_service is None:
            logger.warning(
                "Qdrant service unavailable; semantic duplication check will be skipped."
            )
        else:
            # Attach service to context for the rule engine to use
            auditor_context.qdrant_service = qdrant_service

        # 3. Extract all executable rules
        # FIX: Added enforcement_loader parameter
        all_rules = extract_executable_rules(
            auditor_context.policies, auditor_context.enforcement_loader
        )

        # 4. Find AST duplication rule
        ast_rule = next(
            (r for r in all_rules if r.rule_id == "purity.no_ast_duplication"),
            None,
        )

        # 5. Find semantic duplication rule
        semantic_rule = next(
            (r for r in all_rules if r.rule_id == "purity.no_semantic_duplication"),
            None,
        )

        all_findings: list[AuditFinding] = []

        # 6. Execute AST duplication check
        if ast_rule:
            logger.info("Running AST duplication check...")
            ast_rule.params["threshold"] = threshold
            ast_findings = await execute_rule(ast_rule, auditor_context)
            all_findings.extend(ast_findings)
            logger.info("AST check found %d duplicate pairs", len(ast_findings))

        # 7. Execute semantic duplication check
        if semantic_rule and qdrant_service:
            logger.info("Running semantic duplication check...")
            semantic_rule.params["threshold"] = threshold
            semantic_findings = await execute_rule(semantic_rule, auditor_context)
            all_findings.extend(semantic_findings)
            logger.info(
                "Semantic check found %d duplicate pairs", len(semantic_findings)
            )

        # 8. Report results
        if not all_findings:
            logger.info("✅ No significant duplicates found (threshold=%s).", threshold)
            return

        logger.info("⚠️  Found %s total duplication finding(s).", len(all_findings))

        # 9. Group findings into clusters for better readability
        grouped = _group_findings(all_findings)
        logger.info("Found %s logical cluster(s) of duplicated code:", len(grouped))

        for idx, cluster_findings in enumerate(grouped, start=1):
            logger.info("Cluster %s:", idx)
            for finding in cluster_findings:
                ctx = finding.context or {}
                dup_type = ctx.get("type", "unknown")
                logger.info(
                    "  - [%s] %s <-> %s (similarity: %s)",
                    dup_type.upper(),
                    ctx.get("symbol_a", "???"),
                    ctx.get("symbol_b", "???"),
                    f"{ctx.get('similarity', 0):.2%}",
                )

    except Exception as exc:
        logger.error("Duplication check failed: %s", exc)
        logger.debug(traceback.format_exc())
        raise
