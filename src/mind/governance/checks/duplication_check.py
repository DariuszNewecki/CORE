# src/mind/governance/checks/duplication_check.py
"""
A constitutional audit check to find semantically duplicate symbols using a
vector database, providing evidence for refactoring patterns.
"""

from __future__ import annotations

import asyncio
from typing import Any

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 13cf4ae9-f18b-410f-a320-399cc713f277
class DuplicationCheck(BaseCheck):
    """
    Enforces the 'dry_by_design' principle by finding semantically similar symbols.
    """

    policy_rule_ids = [
        "extract_function",
        "extract_module",
        "introduce_facade",
    ]

    def __init__(
        self, context: AuditorContext, max_concurrent_queries: int = 16
    ) -> None:
        """
        Initialize the duplication check.
        Uses context.services.qdrant if available.
        """
        super().__init__(context)

        # Access services via context (DI Pattern)
        # Assuming context has a .services or similar accessor, or we pass it
        # For now, we'll assume the context carries the service reference or we can't run
        self.qdrant_service = getattr(context, "qdrant_service", None)

        self.symbols: dict[str, dict[str, Any]] = self.context.knowledge_graph.get(
            "symbols", {}
        )

        qa_policy = self.context.policies.get("quality_assurance", {})
        exceptions = qa_policy.get("audit_exceptions", {})

        self.ignored_symbol_keys: set[str] = {
            item["key"]
            for item in exceptions.get("symbol_ignores", [])
            if isinstance(item, dict) and "key" in item
        }

        self._semaphore = asyncio.Semaphore(max_concurrent_queries)

    # ID: 1da6e2c3-fbd4-4860-b95e-7625f426edba
    async def execute(self, threshold: float = 0.85) -> list[AuditFinding]:
        """
        Asynchronously runs the duplication check across all vectorized symbols.
        Headless execution - no UI/progress bars.
        """
        if not self.symbols:
            return []

        if not self.qdrant_service:
            logger.debug(
                "DuplicationCheck: QdrantService not available in context; skipping."
            )
            return []

        symbols_to_check = list(self.symbols.values())
        tasks = [
            self._check_single_symbol(symbol, threshold) for symbol in symbols_to_check
        ]

        # Headless execution using gather
        results_lists = await asyncio.gather(*tasks)

        # Flatten results
        results = [finding for sublist in results_lists for finding in sublist]

        # Deduplicate findings by (symbol_a, symbol_b) pair
        unique_findings: dict[tuple[str, str], AuditFinding] = {}
        for finding in results:
            ctx = finding.context or {}
            key_tuple = tuple(
                sorted(
                    (
                        ctx.get("symbol_a", ""),
                        ctx.get("symbol_b", ""),
                    )
                )
            )
            if all(key_tuple) and key_tuple not in unique_findings:
                unique_findings[key_tuple] = finding

        return list(unique_findings.values())

    async def _check_single_symbol(
        self,
        symbol: dict[str, Any],
        threshold: float,
    ) -> list[AuditFinding]:
        """Checks a single symbol for duplicates against the Qdrant index."""
        findings: list[AuditFinding] = []

        symbol_key = symbol.get("symbol_path")
        vector_id = symbol.get("vector_id")

        if not symbol_key or not vector_id or symbol_key in self.ignored_symbol_keys:
            return findings

        async with self._semaphore:
            try:
                # Assuming get_vector_by_id returns just the vector (list[float])
                query_vector = await self.qdrant_service.get_vector_by_id(
                    point_id=str(vector_id)
                )
                if not query_vector:
                    return findings

                similar_hits = await self.qdrant_service.search_similar(
                    query_vector=query_vector,
                    limit=5,
                )

                for hit in similar_hits:
                    payload = hit.get("payload") or {}
                    score = float(hit.get("score", 0.0))
                    hit_symbol_key = payload.get("chunk_id")

                    if (
                        not hit_symbol_key
                        or hit_symbol_key == symbol_key
                        or hit_symbol_key in self.ignored_symbol_keys
                    ):
                        continue

                    if score > threshold:
                        symbol_a, symbol_b = sorted((symbol_key, hit_symbol_key))
                        findings.append(
                            AuditFinding(
                                check_id="code_standards.refactoring.semantic_duplication",
                                severity=AuditSeverity.WARNING,
                                message=(
                                    f"Potential duplicate logic found between "
                                    f"'{symbol_a}' and '{symbol_b}' "
                                    f"(similarity: {score:.2f}). Consider refactoring."
                                ),
                                file_path=symbol.get("file_path", "unknown"),
                                context={
                                    "symbol_a": symbol_a,
                                    "symbol_b": symbol_b,
                                    "similarity": f"{score:.2f}",
                                },
                            )
                        )
            except Exception as exc:
                logger.debug("Duplication check failed for '%s': %s", symbol_key, exc)

        return findings
