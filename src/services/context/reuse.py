# src/services/context/reuse.py

"""ReuseFinder – light-weight reuse / duplication hints for ContextPackage.

This module does NOT change behavior of the builder or packets yet.
It provides a small, testable service that:

1. Looks at the current task (target_file + target_symbol).
2. Tries to derive a good "anchor" (AST signature if possible).
3. Uses VectorProvider and DBProvider to find similar symbols.
4. Produces a structured ReuseAnalysis that other components can attach
   to provenance or feed into prompts.

The goal is to support proactive "look before you code" behavior, without
blocking when Qdrant or DB are not available.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .providers import ASTProvider, DBProvider, VectorProvider

logger = logging.getLogger(__name__)


@dataclass
# ID: 3c0b93d2-3b7d-4e4e-8c1d-1c8f8a4f9a35
class ReuseAnalysis:
    """Structured result of a reuse / duplication check."""

    suggestions: list[str] = field(default_factory=list)
    similar_items: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    # ID: b5df7c8e-1e2a-4c8f-bf1d-7ad9d7a3d2f4
    def as_dict(self) -> dict[str, Any]:
        """Convert analysis to a serializable dict."""
        return {
            "suggestions": self.suggestions,
            "similar_items": self.similar_items,
            "notes": self.notes,
        }


# ID: 0a5a8d6f-7bb4-4c0b-87a5-1fc0e9b9a2f1
class ReuseFinder:
    """Finds potential reuse / duplication candidates for a given task.

    This is intentionally conservative:
    - If Qdrant or DB are not configured, it degrades to "no strong hints".
    - It never raises on failures; it logs and returns an empty analysis instead.
    """

    def __init__(
        self,
        db_provider: DBProvider | None = None,
        vector_provider: VectorProvider | None = None,
        ast_provider: ASTProvider | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.db_provider = db_provider
        self.vector_provider = vector_provider
        self.ast_provider = ast_provider
        self.config = config or {}

    # ID: 4b9e8c86-2d6b-4f3a-9f53-9e1d15c8a3b0
    async def analyze_task(self, task_spec: dict[str, Any]) -> ReuseAnalysis:
        """Analyze a task for possible reuse / duplication.

        Expected task_spec fields (best effort, all optional):
        - target_symbol: name of the function/class we are working on
        - target_file:   path to the file (relative to repo root)

        Returns:
            ReuseAnalysis with suggestions, similar_items, and notes.
        """
        analysis = ReuseAnalysis()

        target_symbol = task_spec.get("target_symbol")
        target_file = task_spec.get("target_file")

        if not target_symbol or not target_file:
            analysis.notes.append(
                "ReuseFinder: task_spec missing 'target_symbol' or 'target_file'; "
                "skipping reuse analysis."
            )
            return analysis

        logger.info("Running reuse analysis for %s in %s", target_symbol, target_file)

        # 1) Derive an anchor text – start with a simple description.
        anchor_text = f"{target_symbol} in {target_file}"

        # Try to upgrade to an AST signature if we can.
        if self.ast_provider is not None:
            try:
                signature = self.ast_provider.get_signature(target_file, target_symbol)
                if signature:
                    anchor_text = signature
                    analysis.notes.append(
                        "ReuseFinder: using AST signature as anchor text."
                    )
                else:
                    analysis.notes.append(
                        "ReuseFinder: no AST signature found; using fallback anchor."
                    )
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("ReuseFinder AST lookup failed: %s", exc, exc_info=True)
                analysis.notes.append(
                    "ReuseFinder: AST lookup failed; using fallback anchor."
                )
        else:
            analysis.notes.append(
                "ReuseFinder: no ASTProvider configured; using fallback anchor."
            )

        # 2) Check for exact or near-exact matches in the symbol DB.
        if self.db_provider is not None and target_symbol:
            try:
                existing = await self.db_provider.get_symbol_by_name(target_symbol)
                if existing:
                    # Ensure we don't double-add if vector search also returns it later.
                    if not _contains_item(analysis.similar_items, existing):
                        analysis.similar_items.append(existing)

                    path = existing.get("path") or existing.get("name")
                    analysis.suggestions.append(
                        f"Existing symbol with the same name found at '{path}'. "
                        "Consider reusing or extending it instead of creating a new one."
                    )
                    analysis.notes.append(
                        "ReuseFinder: DBProvider reported an existing symbol "
                        "with the same name."
                    )
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("ReuseFinder DB lookup failed: %s", exc, exc_info=True)
                analysis.notes.append(
                    "ReuseFinder: DB lookup failed; reuse hints may be incomplete."
                )
        else:
            analysis.notes.append(
                "ReuseFinder: DBProvider not configured; skipping DB symbol lookup."
            )

        # 3) Ask Qdrant for semantically similar symbols based on the anchor.
        if self.vector_provider is not None:
            try:
                top_k = int(self.config.get("reuse_top_k", 8))
                neighbors = await self.vector_provider.search_similar(
                    anchor_text, top_k=top_k
                )
                if neighbors:
                    for item in neighbors:
                        if not _contains_item(analysis.similar_items, item):
                            analysis.similar_items.append(item)

                    analysis.suggestions.append(
                        "Review the similar symbols found in the codebase "
                        "before introducing new helpers or modules."
                    )
                    analysis.notes.append(
                        f"ReuseFinder: Qdrant returned {len(neighbors)} neighbors."
                    )
                else:
                    analysis.notes.append(
                        "ReuseFinder: Qdrant returned no neighbors for this anchor."
                    )
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("ReuseFinder vector search failed: %s", exc, exc_info=True)
                analysis.notes.append(
                    "ReuseFinder: vector search failed; reuse hints may be incomplete."
                )
        else:
            analysis.notes.append(
                "ReuseFinder: VectorProvider not configured; skipping semantic search."
            )

        # 4) If we still have no concrete suggestions, provide a neutral one.
        if not analysis.suggestions:
            analysis.suggestions.append(
                "No strong reuse candidates were found. "
                "Proceed with new implementation, but keep it small and composable."
            )

        return analysis

    # ID: 9f6d1a4c-2e8a-4c9a-9a9e-5e4b8f3b1d20
    def summarize_for_prompt(self, analysis: ReuseAnalysis) -> str:
        """Render a concise, LLM-friendly summary of reuse hints.

        This text is meant to be embedded into the prompt header, not to drive
        behavior by itself. It should be short and declarative.
        """
        if not analysis.suggestions and not analysis.similar_items:
            return (
                "Reuse hints: No strong reuse candidates were found in the "
                "existing codebase."
            )

        lines: list[str] = ["Reuse hints:"]

        for suggestion in analysis.suggestions:
            lines.append(f"- {suggestion}")

        max_items = int(self.config.get("reuse_max_items_in_prompt", 5))
        for item in analysis.similar_items[:max_items]:
            name = item.get("name", "unknown")
            path = item.get("path") or item.get("name", "unknown")
            score = item.get("score")
            if score is not None:
                lines.append(f"  • {name} ({path}, score={score:.3f})")
            else:
                lines.append(f"  • {name} ({path})")

        return "\n".join(lines)


def _contains_item(items: list[dict[str, Any]], candidate: dict[str, Any]) -> bool:
    """Helper to deduplicate similar_items by (name, path)."""
    cand_name = candidate.get("name")
    cand_path = candidate.get("path")
    for item in items:
        if item.get("name") == cand_name and item.get("path") == cand_path:
            return True
    return False
