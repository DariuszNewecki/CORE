# src/will/workers/violation_remediator_body/context.py
"""
Context building for ViolationRemediator.

Responsibility: assemble call-graph and semantic context for a violating file.
No LLM remediation calls. No file writes. No Blackboard writes.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)

_CODE_COLLECTION = "core-code"
_SEMANTIC_EXAMPLES_LIMIT = 3


# ID: 4b9c5641-7688-451c-9b3f-09f2c773098d
class ContextMixin:
    """
    Mixin providing context-assembly methods for ViolationRemediator.

    Requires self._ctx to be set by the host class.
    """

    async def _build_context(self, file_path: str, violations_summary: str) -> str:
        """
        Build a context package for the violating file combining:
        1. Call graph context (ContextService - structural neighbours)
        2. Semantic examples (Qdrant core-code - similar correct implementations)
        """
        parts: list[str] = []

        try:
            ctx_service = self._ctx.context_service
            call_graph_ctx = await ctx_service.get_context_for_file(file_path)
            if call_graph_ctx:
                parts.append(f"=== Call graph context ===\n{call_graph_ctx}")
        except Exception as exc:
            logger.debug(
                "ViolationRemediator: call graph context unavailable for %s - %s",
                file_path,
                exc,
            )

        try:
            qdrant = self._ctx.vector_store
            hits = await qdrant.search(
                collection=_CODE_COLLECTION,
                query=violations_summary,
                limit=_SEMANTIC_EXAMPLES_LIMIT,
            )
            if hits:
                examples = "\n\n".join(
                    h.payload.get("source", "") for h in hits if h.payload
                )
                parts.append(
                    f"=== Semantic examples (correct implementations) ===\n{examples}"
                )
        except Exception as exc:
            logger.debug(
                "ViolationRemediator: semantic context unavailable for %s - %s",
                file_path,
                exc,
            )

        return "\n\n".join(parts) if parts else ""
