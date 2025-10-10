# src/features/governance/checks/duplication_check.py
"""
A constitutional audit check to find semantically duplicate or near-duplicate
symbols (functions/classes) using the Qdrant vector database.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import networkx as nx
from rich.progress import track
from services.clients.qdrant_client import QdrantService
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity

from features.governance.audit_context import AuditorContext

log = getLogger("duplication_check")


def _group_findings(findings: list[AuditFinding]) -> List[List[AuditFinding]]:
    """Groups individual finding pairs into clusters of related duplicates."""
    graph = nx.Graph()
    finding_map = {}

    for finding in findings:
        # The context dictionary is the reliable source for symbol keys.
        symbol1 = finding.context.get("symbol_a")
        symbol2 = finding.context.get("symbol_b")
        if symbol1 and symbol2:
            graph.add_edge(symbol1, symbol2)
            # Store the finding under a canonical key (sorted tuple).
            finding_map[tuple(sorted((symbol1, symbol2)))] = finding

    # Find connected components (these are our clusters).
    clusters = list(nx.connected_components(graph))
    grouped_findings = []

    for cluster in clusters:
        cluster_findings = []
        # Reconstruct the findings that belong to this cluster.
        for i, node1 in enumerate(list(cluster)):
            for node2 in list(cluster)[i + 1 :]:
                key = tuple(sorted((node1, node2)))
                if key in finding_map:
                    cluster_findings.append(finding_map[key])

        if cluster_findings:
            # Sort by similarity score (descending) for consistent reporting.
            cluster_findings.sort(
                key=lambda f: float(f.context.get("similarity", 0)), reverse=True
            )
            grouped_findings.append(cluster_findings)

    return grouped_findings


# ID: 80fe0586-c41f-4319-a09b-d8419b7b3f38
class DuplicationCheck:
    """
    Enforces the 'dry_by_design' principle by finding semantically similar symbols.
    """

    def __init__(self, context: AuditorContext):
        self.context = context
        self.symbols = self.context.knowledge_graph.get("symbols", {})
        self.qdrant_service = QdrantService()
        ignore_policy = self.context.policies.get("audit_ignore_policy", {})
        self.ignored_symbol_keys = {
            item["key"]
            for item in ignore_policy.get("symbol_ignores", [])
            if "key" in item
        }

    async def _check_single_symbol(
        self, symbol: Dict[str, Any], threshold: float
    ) -> List[AuditFinding]:
        """Checks a single symbol for duplicates against the Qdrant index."""
        findings = []
        symbol_key = symbol.get("symbol_path")
        vector_id = symbol.get("vector_id")

        # --- THIS IS THE FIX ---
        # Do not proceed if there is no vector_id for this symbol.
        if not vector_id or symbol_key in self.ignored_symbol_keys:
            return []
        # --- END OF FIX ---

        try:
            query_vector = await self.qdrant_service.get_vector_by_id(
                point_id=vector_id
            )
            if not query_vector:
                # This handles cases where the vector exists in PG but not Qdrant
                log.warning(f"Could not retrieve vector for point ID {vector_id}:")
                return []

            similar_hits = await self.qdrant_service.search_similar(
                query_vector=query_vector, limit=5
            )

            for hit in similar_hits:
                # The payload for vectors now uses 'chunk_id' to store the symbol_path.
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

    # ID: ecce6b93-2340-48cd-b787-ce24ff944620
    async def execute(self, threshold: float = 0.80) -> List[AuditFinding]:
        """
        Asynchronously runs the duplication check across all vectorized symbols.
        """
        # Ensure we only check symbols that are supposed to have a vector.
        vectorized_symbols = [s for s in self.symbols.values() if s.get("vector_id")]

        if not vectorized_symbols:
            return []

        tasks = [
            self._check_single_symbol(symbol, threshold)
            for symbol in vectorized_symbols
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
