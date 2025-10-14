# src/features/governance/checks/duplication_check.py
"""
A constitutional audit check to find semantically duplicate or near-duplicate
symbols (functions/classes) using the Qdrant vector database.
"""

from __future__ import annotations

import asyncio
from typing import Any

import networkx as nx
from rich.progress import track

from features.governance.audit_context import AuditorContext
from services.clients.qdrant_client import QdrantService
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity

log = getLogger("duplication_check")


def _group_findings(findings: list[AuditFinding]) -> list[list[AuditFinding]]:
    """Groups individual finding pairs into clusters of related duplicates."""
    # This helper function is correct and does not need changes.
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
            cluster_findings.sort(
                key=lambda f: float(f.context.get("similarity", 0)), reverse=True
            )
            grouped_findings.append(cluster_findings)

    return grouped_findings


# ID: 79150815-dfca-4b22-9b01-bdc01d14702e
class DuplicationCheck:
    """
    Enforces the 'dry_by_design' principle by finding semantically similar symbols.
    """

    def __init__(self, context: AuditorContext):
        self.context = context
        self.symbols = self.context.knowledge_graph.get("symbols", {})
        # --- FIX: We no longer create a shared client here. ---
        # self.qdrant_service = QdrantService()
        ignore_policy = self.context.policies.get("audit_ignore_policy", {})
        self.ignored_symbol_keys = {
            item["key"]
            for item in ignore_policy.get("symbol_ignores", [])
            if "key" in item
        }

    async def _check_single_symbol(
        self, symbol: dict[str, Any], threshold: float
    ) -> list[AuditFinding]:
        """Checks a single symbol for duplicates against the Qdrant index."""
        findings = []
        symbol_key = symbol.get("symbol_path")

        # --- THIS IS THE DEFINITIVE FIX ---
        # Each concurrent task now gets its own private, fresh client instance.
        qdrant_service = QdrantService()
        # --- END OF FIX ---

        point_id = str(symbol.get("vector_id")) if symbol.get("vector_id") else None

        if not point_id or symbol_key in self.ignored_symbol_keys:
            return []

        try:
            query_vector = await qdrant_service.get_vector_by_id(point_id=point_id)
            if not query_vector:
                return []

            similar_hits = await qdrant_service.search_similar(
                query_vector=query_vector, limit=5
            )

            for hit in similar_hits:
                if not hit.get("payload"):
                    continue

                hit_symbol_key = hit["payload"].get("chunk_id")
                if (
                    not hit_symbol_key
                    or hit_symbol_key == symbol_key
                    or hit_symbol_key in self.ignored_symbol_keys
                ):
                    continue

                if hit["score"] > threshold:
                    if symbol_key < hit_symbol_key:
                        symbol_a, symbol_b = symbol_key, hit_symbol_key
                    else:
                        symbol_a, symbol_b = hit_symbol_key, symbol_key

                    findings.append(
                        AuditFinding(
                            check_id="code.style.semantic-duplication",
                            severity=AuditSeverity.WARNING,
                            message=f"Potential duplicate logic found between '{symbol_a.split('::')[-1]}' and '{symbol_b.split('::')[-1]}'.",
                            file_path=symbol.get("file_path"),
                            context={
                                "symbol_a": symbol_a,
                                "symbol_b": symbol_b,
                                "similarity": f"{hit['score']:.2f}",
                            },
                        )
                    )
        except Exception as e:
            log.warning(f"Could not perform duplication check for '{symbol_key}': {e}")

        return findings

    # ID: a74388ba-140f-4cf6-aa58-de9d61374038
    async def execute(self, threshold: float = 0.80) -> list[AuditFinding]:
        """
        Asynchronously runs the duplication check across all vectorized symbols.
        """
        symbols_to_check = list(self.symbols.values())

        if not symbols_to_check:
            return []

        tasks = [
            self._check_single_symbol(symbol, threshold) for symbol in symbols_to_check
        ]

        results = []
        for future in track(
            asyncio.as_completed(tasks),
            description="Checking for duplicate code...",
            total=len(tasks),
        ):
            results.extend(await future)

        unique_findings = {}
        for finding in results:
            key_tuple = tuple(
                sorted((finding.context["symbol_a"], finding.context["symbol_b"]))
            )
            if key_tuple not in unique_findings:
                unique_findings[key_tuple] = finding

        return list(unique_findings.values())
