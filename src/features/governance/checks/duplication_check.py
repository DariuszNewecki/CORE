# src/features/governance/checks/duplication_check.py
"""
A constitutional audit check to find semantically duplicate or near-duplicate
symbols (functions/classes) using the Qdrant vector database.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from rich.progress import track
from services.clients.qdrant_client import QdrantService
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity

from features.governance.audit_context import AuditorContext

log = getLogger("duplication_check")


# ID: 16e4e42b-3f70-444f-933e-ec1679cd8992
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

        if not vector_id or symbol_key in self.ignored_symbol_keys:
            return []

        try:
            query_vector = await self.qdrant_service.get_vector_by_id(
                point_id=vector_id
            )
            if not query_vector:
                return []

            similar_hits = await self.qdrant_service.search_similar(
                query_vector=query_vector, limit=5
            )

            for hit in similar_hits:
                hit_symbol_key = hit["payload"]["chunk_id"]
                if (
                    hit_symbol_key == symbol_key
                    or hit_symbol_key in self.ignored_symbol_keys
                ):
                    continue

                if hit["score"] > threshold:
                    if symbol_key < hit_symbol_key:
                        findings.append(
                            AuditFinding(
                                check_id="code.style.semantic-duplication",
                                severity=AuditSeverity.WARNING,
                                message=f"Potential duplicate logic found between '{symbol_key.split('::')[-1]}' and '{hit_symbol_key.split('::')[-1]}'.",
                                file_path=symbol.get("file_path"),
                                context={
                                    "symbol_a": symbol_key,
                                    "symbol_b": hit_symbol_key,
                                    "similarity": f"{hit['score']:.2f}",
                                },
                            )
                        )
        except Exception as e:
            log.warning(f"Could not perform duplication check for '{symbol_key}': {e}")

        return findings

    # ID: 614e5982-8163-49f9-8762-689960b9851a
    async def execute(self, threshold: float = 0.80) -> List[AuditFinding]:
        """
        Asynchronously runs the duplication check across all vectorized symbols.
        """
        vectorized_symbols = [s for s in self.symbols.values() if s.get("vector_id")]

        if not vectorized_symbols:
            return []

        # This check is computationally intensive, so we process asynchronously.
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

        # Post-process to remove mirrored duplicates (A-B vs B-A)
        unique_findings = {}
        for finding in results:
            key_tuple = tuple(
                sorted((finding.context["symbol_a"], finding.context["symbol_b"]))
            )
            if key_tuple not in unique_findings:
                unique_findings[key_tuple] = finding

        return list(unique_findings.values())
