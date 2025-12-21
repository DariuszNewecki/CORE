# src/mind/governance/checks/duplication_check.py
"""
A constitutional audit check to find semantically duplicate symbols using a
vector database, providing evidence for refactoring patterns.

Ref: .intent/charter/standards/code_standards.json
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

CODE_STANDARDS_POLICY = Path(".intent/charter/standards/code_standards.json")


# ID: semantic-duplication-enforcement
# ID: 4f60e24f-6e49-4e8e-945a-82b6e93a823f
class SemanticDuplicationEnforcement(EnforcementMethod):
    """
    Enforces the 'dry_by_design' principle by finding semantically similar symbols.
    Uses vector similarity search to detect potential code duplication.
    """

    def __init__(
        self,
        rule_id: str,
        severity: AuditSeverity = AuditSeverity.WARNING,
        max_concurrent_queries: int = 16,
    ):
        super().__init__(rule_id, severity)
        self.max_concurrent_queries = max_concurrent_queries

    # ID: 80bd4e0a-5dc8-4f2c-914f-a3da973de157
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        """
        Synchronous wrapper for async verification.
        Accepts threshold as kwarg (e.g., threshold=0.85).
        """
        # Extract threshold from kwargs or use default
        threshold = kwargs.get("threshold", 0.85)

        # Run async check
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context - can't run nested
                logger.warning("Cannot run duplication check in nested async context")
                return []
            else:
                return loop.run_until_complete(
                    self._verify_async(context, rule_data, threshold)
                )
        except RuntimeError:
            # No event loop available
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    self._verify_async(context, rule_data, threshold)
                )
            finally:
                loop.close()

    async def _verify_async(
        self, context: AuditorContext, rule_data: dict[str, Any], threshold: float
    ) -> list[AuditFinding]:
        """
        Asynchronously runs the duplication check across all vectorized symbols.
        """
        findings = []

        # Get symbols from knowledge graph
        symbols = context.knowledge_graph.get("symbols", {})
        if not symbols:
            return findings

        # Get Qdrant service from context
        qdrant_service = getattr(context, "qdrant_service", None)
        if not qdrant_service:
            logger.debug(
                "DuplicationCheck: QdrantService not available in context; skipping."
            )
            return findings

        # Get ignored symbols from policy
        qa_policy = context.policies.get("quality_assurance", {})
        exceptions = qa_policy.get("audit_exceptions", {})
        ignored_symbol_keys: set[str] = {
            item["key"]
            for item in exceptions.get("symbol_ignores", [])
            if isinstance(item, dict) and "key" in item
        }

        # Check all symbols
        semaphore = asyncio.Semaphore(self.max_concurrent_queries)
        symbols_to_check = list(symbols.values())
        tasks = [
            self._check_single_symbol(
                symbol, threshold, qdrant_service, ignored_symbol_keys, semaphore
            )
            for symbol in symbols_to_check
        ]

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
        qdrant_service: Any,
        ignored_symbol_keys: set[str],
        semaphore: asyncio.Semaphore,
    ) -> list[AuditFinding]:
        """Checks a single symbol for duplicates against the Qdrant index."""
        findings: list[AuditFinding] = []

        symbol_key = symbol.get("symbol_path")
        vector_id = symbol.get("vector_id")

        if not symbol_key or not vector_id or symbol_key in ignored_symbol_keys:
            return findings

        async with semaphore:
            try:
                query_vector = await qdrant_service.get_vector_by_id(
                    point_id=str(vector_id)
                )
                if not query_vector:
                    return findings

                similar_hits = await qdrant_service.search_similar(
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
                        or hit_symbol_key in ignored_symbol_keys
                    ):
                        continue

                    if score > threshold:
                        symbol_a, symbol_b = sorted((symbol_key, hit_symbol_key))
                        findings.append(
                            self._create_finding(
                                message=(
                                    f"Potential duplicate logic found between "
                                    f"'{symbol_a}' and '{symbol_b}' "
                                    f"(similarity: {score:.2f}). Consider refactoring."
                                ),
                                file_path=symbol.get("file_path", "unknown"),
                            )
                        )
            except Exception as exc:
                logger.debug("Duplication check failed for '%s': %s", symbol_key, exc)

        return findings


# ID: 13cf4ae9-f18b-410f-a320-399cc713f277
class DuplicationCheck(RuleEnforcementCheck):
    """
    Enforces the 'dry_by_design' principle by finding semantically similar symbols.

    Ref: .intent/charter/standards/code_standards.json

    Usage:
        check = DuplicationCheck(context)
        findings = await check.execute(threshold=0.85)  # Custom threshold
    """

    policy_rule_ids: ClassVar[list[str]] = [
        "refactor.semantic_duplication",
    ]

    policy_file: ClassVar[Path] = CODE_STANDARDS_POLICY

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        SemanticDuplicationEnforcement(
            rule_id="refactor.semantic_duplication",
            severity=AuditSeverity.WARNING,
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True

    # Override execute to support async properly
    # ID: 52ac2cb9-9197-448a-9521-e0f2c8b1baca
    async def execute(self, **kwargs) -> list[AuditFinding]:
        """
        Async wrapper that calls parent's sync execute.
        Parent will call enforcement method which handles async internally.
        """
        # Call parent's synchronous execute, which will call verify()
        # verify() handles its own async logic
        return super().execute(**kwargs)
