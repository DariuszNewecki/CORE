# src/mind/governance/checks/duplication_check.py
"""
A constitutional audit check to find semantically duplicate symbols using a
vector database, providing evidence for refactoring patterns.
"""

from __future__ import annotations

import asyncio
from typing import Any

from rich.progress import track

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.base_check import BaseCheck
from services.clients.qdrant_client import QdrantService
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


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

    def __init__(
        self,
        context: AuditorContext | None = None,
        qdrant_service: QdrantService | None = None,
        *,
        auditor_context: AuditorContext | None = None,
        max_concurrent_queries: int = 16,
    ) -> None:
        """
        Initialize the duplication check.

        Supports both:
          - DuplicationCheck(context, qdrant_service)
          - DuplicationCheck(auditor_context=..., qdrant_service=...)

        `qdrant_service` may be None; in that case the check safely no-ops.
        """
        # Backwards-compatible resolution of the context argument
        if context is None and auditor_context is not None:
            context = auditor_context
        if context is None:
            raise ValueError("DuplicationCheck requires an AuditorContext")

        super().__init__(context)
        self.qdrant_service = qdrant_service

        # Symbols as exposed by core.knowledge_graph (DB SSOT)
        self.symbols: dict[str, dict[str, Any]] = self.context.knowledge_graph.get(
            "symbols", {}
        )

        # FIX: Load from quality_assurance -> audit_exceptions -> symbol_ignores
        qa_policy = self.context.policies.get("quality_assurance", {})
        exceptions = qa_policy.get("audit_exceptions", {})

        self.ignored_symbol_keys: set[str] = {
            item["key"]
            for item in exceptions.get("symbol_ignores", [])
            if isinstance(item, dict) and "key" in item
        }

        # Throttle concurrent Qdrant calls to avoid hammering the service
        self._semaphore = asyncio.Semaphore(max_concurrent_queries)

    async def _check_single_symbol(
        self,
        symbol: dict[str, Any],
        threshold: float,
    ) -> list[AuditFinding]:
        """
        Checks a single symbol for duplicates against the Qdrant index.

        Uses the DB-backed `vector_id` field as the Qdrant point ID, *not* the
        symbol's UUID. This keeps the check in lock-step with the SSOT
        (core.symbol_vector_links + Qdrant).
        """
        findings: list[AuditFinding] = []

        symbol_key = symbol.get("symbol_path")
        vector_id = symbol.get("vector_id")

        # Skip if we don't have a proper symbol key or a vector binding,
        # or if this symbol is explicitly ignored by policy.
        if not symbol_key or not vector_id or symbol_key in self.ignored_symbol_keys:
            return findings

        if not self.qdrant_service:
            logger.info(
                "DuplicationCheck: QdrantService not available; "
                "skipping semantic duplicate check for %s",
                symbol_key,
            )
            return findings

        async with self._semaphore:
            try:
                # NOTE: vector_id comes from DB (core.symbol_vector_links.vector_id)
                query_vector = await self.qdrant_service.get_vector_by_id(
                    point_id=str(vector_id)
                )
                if not query_vector:
                    # If the vector is unexpectedly missing, just skip this symbol.
                    logger.warning(
                        "DuplicationCheck: No vector returned for '%s' "
                        "(vector_id=%s); skipping symbol.",
                        symbol_key,
                        vector_id,
                    )
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
                                # A more structured ID indicating a prompt for refactoring.
                                check_id=(
                                    "code_standards.refactoring.semantic_duplication"
                                ),
                                severity=AuditSeverity.WARNING,
                                message=(
                                    "Potential duplicate logic found between "
                                    f"'{symbol_a.split('::')[-1]}' and "
                                    f"'{symbol_b.split('::')[-1]}'."
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
            except Exception as exc:  # pragma: no cover - defensive logging
                # We deliberately treat this as a *soft* failure for a single symbol;
                # the audit as a whole should continue even if a subset of vectors
                # cannot be retrieved or searched.
                logger.warning(
                    (
                        "Could not perform duplication check for '%s' "
                        "(vector_id=%s): %s"
                    ),
                    symbol_key,
                    vector_id,
                    exc,
                )

        return findings

    # ID: 1da6e2c3-fbd4-4860-b95e-7625f426edba
    async def execute(self, threshold: float = 0.85) -> list[AuditFinding]:
        """
        Asynchronously runs the duplication check across all vectorized symbols.

        The flow is:
        1. Iterate over all symbols coming from core.knowledge_graph.
        2. For each symbol with a valid `vector_id`, retrieve its vector from Qdrant.
        3. Run a similarity search and generate pairwise findings above the threshold.
        4. Deduplicate findings so each (symbol_a, symbol_b) pair appears once.
        """
        if not self.symbols:
            return []

        if not self.qdrant_service:
            logger.info(
                "DuplicationCheck: QdrantService not available; "
                "skipping entire semantic duplication check."
            )
            return []

        symbols_to_check = list(self.symbols.values())
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
