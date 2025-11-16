# src/mind/governance/checks/duplication_check.py
"""
A constitutional audit check to find semantically duplicate symbols using a
vector database, providing evidence for refactoring patterns.
"""

from __future__ import annotations

import asyncio
from typing import Any

from rich.progress import track
from services.clients.qdrant_client import QdrantService
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.base_check import BaseCheck

logger = getLogger(__name__)


# ID: 13cf4ae9-f18b-410f-a320-399cc713f277
class DuplicationCheck(BaseCheck):
    """
    Enforces the 'dry_by_design' principle by finding semantically similar symbols,
    triggering refactoring patterns like 'extract_function' and 'extract_module'.
    """

    # Fulfills the contract from BaseCheck. This check provides the evidence
    # that informs the need for these refactoring patterns.
    policy_rule_ids = [
        "extract_function",
        "extract_module",
        "introduce_facade",
    ]

    def __init__(self, context: AuditorContext, qdrant_service: QdrantService) -> None:
        super().__init__(context)
        self.qdrant_service = qdrant_service
        self.symbols: dict[str, dict[str, Any]] = self.context.knowledge_graph.get(
            "symbols", {}
        )

        # Get ignore configuration from the central context, not by loading it here.
        # This assumes the AuditorContext is responsible for loading the ignore policy.
        ignore_policy = self.context.policies.get("audit_ignore_policy", {})
        self.ignored_symbol_keys = {
            item["key"]
            for item in ignore_policy.get("symbol_ignores", [])
            if isinstance(item, dict) and "key" in item
        }

    async def _check_single_symbol(
        self, symbol: dict[str, Any], threshold: float
    ) -> list[AuditFinding]:
        """Checks a single symbol for duplicates against the Qdrant index."""
        findings: list[AuditFinding] = []
        symbol_key = symbol.get("symbol_path")
        point_id = str(symbol.get("uuid")) if symbol.get("uuid") else None

        if not symbol_key or not point_id or symbol_key in self.ignored_symbol_keys:
            return findings

        try:
            query_vector = await self.qdrant_service.get_vector_by_id(point_id=point_id)
            if not query_vector:
                return findings

            similar_hits = await self.qdrant_service.search_similar(
                query_vector=query_vector, limit=5
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
                            # A more structured ID indicating a prompt for refactoring.
                            check_id="code_standards.refactoring.semantic_duplication",
                            severity=AuditSeverity.WARNING,
                            message=(
                                "Potential duplicate logic found between "
                                f"'{symbol_a.split('::')[-1]}' and '{symbol_b.split('::')[-1]}'."
                            ),
                            file_path=symbol.get("file_path"),
                            context={
                                "symbol_a": symbol_a,
                                "symbol_b": symbol_b,
                                "similarity": f"{score:.2f}",
                                "suggested_actions": self.policy_rule_ids,
                            },
                        )
                    )
        except Exception as exc:
            logger.warning(
                "Could not perform duplication check for '%s': %s", symbol_key, exc
            )

        return findings

    # ID: 1da6e2c3-fbd4-4860-b95e-7625f426edba
    async def execute(self, threshold: float = 0.85) -> list[AuditFinding]:
        """Asynchronously runs the duplication check across all vectorized symbols."""
        symbols_to_check = list(self.symbols.values())
        if not symbols_to_check:
            return []

        tasks = [
            self._check_single_symbol(symbol, threshold) for symbol in symbols_to_check
        ]
        results: list[AuditFinding] = []

        for future in track(
            asyncio.as_completed(tasks),
            description="Checking for duplicate code...",
            total=len(tasks),
        ):
            results.extend(await future)

        # Deduplicate findings by (symbol_a, symbol_b) pair
        unique_findings: dict[tuple[str, str], AuditFinding] = {}
        for finding in results:
            ctx = finding.context or {}
            key_tuple = tuple(
                sorted((ctx.get("symbol_a", ""), ctx.get("symbol_b", "")))
            )
            if all(key_tuple) and key_tuple not in unique_findings:
                unique_findings[key_tuple] = finding

        return list(unique_findings.values())
