# src/features/governance/checks/duplication_check.py
"""
A constitutional audit check to find semantically duplicate or near-duplicate
symbols (functions/classes) using the Qdrant vector database.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from rich.progress import track

from features.governance.audit_context import AuditorContext
from services.clients.qdrant_client import QdrantService
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity

log = getLogger("duplication_check")

# The similarity score above which two symbols are considered near-duplicates.
# TODO: This should be moved to a constitutional policy file.
SIMILARITY_THRESHOLD = 0.80


# ID: 16e4e42b-3f70-444f-933e-ec1679cd8992
class DuplicationCheck:
    """
    Enforces the 'dry_by_design' principle by finding semantically similar symbols.
    """

    def __init__(self, context: AuditorContext):
        self.context = context
        self.symbols = self.context.knowledge_graph.get("symbols", {})
        self.qdrant_service = QdrantService()

    async def _check_single_symbol(self, symbol: Dict[str, Any]) -> List[AuditFinding]:
        """Checks a single symbol for duplicates against the Qdrant index."""
        findings = []
        symbol_key = symbol.get("symbol_path")  # Use symbol_path for consistency
        vector_id = symbol.get("vector_id")

        if not vector_id:
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
                if hit_symbol_key == symbol_key:
                    continue

                if hit["score"] > SIMILARITY_THRESHOLD:
                    if symbol_key < hit_symbol_key:
                        findings.append(
                            AuditFinding(
                                check_id="duplication.semantic.near_duplicate_found",
                                severity=AuditSeverity.WARNING,
                                message=(
                                    f"Potential duplicate logic found between '{symbol_key}' and "
                                    f"'{hit_symbol_key}' (Similarity: {hit['score']:.2f})"
                                ),
                                file_path=symbol.get("file"),
                            )
                        )
        except Exception as e:
            log.warning(f"Could not perform duplication check for '{symbol_key}': {e}")

        return findings

    # ID: 614e5982-8163-49f9-8762-689960b9851a
    async def execute(self) -> List[AuditFinding]:
        """
        Asynchronously runs the duplication check across all vectorized symbols.
        """
        vectorized_symbols = [s for s in self.symbols.values() if s.get("vector_id")]

        if not vectorized_symbols:
            return []

        tasks = [self._check_single_symbol(symbol) for symbol in vectorized_symbols]

        results = []
        for future in track(
            asyncio.as_completed(tasks),
            description="Checking for duplicate code...",
            total=len(tasks),
        ):
            results.extend(await future)
        return results
