# src/will/agents/reconnaissance_agent.py

"""
Implements the ReconnaissanceAgent, which performs targeted queries and semantic
search against the knowledge graph to build a minimal, surgical context for the Planner.
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)


# ID: 95a1c3e0-d1fe-4a45-b85d-183967c80ae2
class ReconnaissanceAgent:
    """Queries the knowledge graph to build a focused context for a task."""

    def __init__(
        self, knowledge_graph: dict[str, Any], cognitive_service: CognitiveService
    ):
        """Initializes with the knowledge graph and cognitive service for search."""
        self.graph = knowledge_graph
        self.symbols = knowledge_graph.get("symbols", {})
        self.cognitive_service = cognitive_service

    async def _find_relevant_symbols_and_files(
        self, goal: str
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Performs a semantic search to find symbols and files relevant to the goal."""
        logger.info("   -> Performing semantic search for relevant context...")
        try:
            search_results = await self.cognitive_service.search_capabilities(
                goal, limit=5
            )
            if not search_results:
                return ([], [])
            relevant_symbols = []
            relevant_files = set()
            for hit in search_results:
                if (payload := hit.get("payload")) and (
                    symbol_key := payload.get("symbol")
                ):
                    if symbol_data := self.symbols.get(symbol_key):
                        relevant_symbols.append(symbol_data)
                        relevant_files.add(symbol_data.get("file"))
            logger.info(f"   -> Found relevant files: {list(relevant_files)}")
            logger.info(
                f"   -> Found relevant symbols: {[s.get('key') for s in relevant_symbols]}"
            )
            return (relevant_symbols, sorted(list(relevant_files)))
        except Exception as e:
            logger.warning("Semantic search for context failed: %s", e)
            return ([], [])

    # ID: c4f6267a-2c91-4dd6-929e-967cc2794cfb
    async def generate_report(self, goal: str) -> str:
        """
        Analyzes a goal, queries the graph, and generates a surgical context report.
        """
        logger.info("🔬 Conducting reconnaissance for goal: '%s'", goal)
        target_symbols, relevant_files = await self._find_relevant_symbols_and_files(
            goal
        )
        report_parts = ["# Reconnaissance Report"]
        if relevant_files:
            report_parts.append("\n## Relevant Files Identified by Semantic Search:")
            for file in relevant_files:
                report_parts.append(f"- `{file}`")
        else:
            report_parts.append(
                "\n- No specific relevant files were identified via semantic search."
            )
        if not target_symbols:
            report_parts.append(
                "\n- No specific code symbols were identified via semantic search."
            )
        else:
            report_parts.append("\n## Relevant Symbols Identified by Semantic Search:")
            for symbol_data in target_symbols:
                callers = self._find_callers(symbol_data.get("name"))
                report_parts.append(f"\n### Symbol: `{symbol_data.get('key', 'N/A')}`")
                report_parts.append(f"- **Type:** {symbol_data.get('type')}")
                report_parts.append(f"- **Location:** `{symbol_data.get('file')}`")
                report_parts.append(f"- **Intent:** {symbol_data.get('intent')}")
                if callers:
                    report_parts.append("- **Referenced By:**")
                    for caller in callers:
                        report_parts.append(f"  - `{caller.get('key')}`")
                else:
                    report_parts.append(
                        "- **Referenced By:** None. This symbol appears to be unreferenced."
                    )
        report_parts.append(
            "\n---\n**Conclusion:** The analysis is complete. Use this information to form a precise plan."
        )
        report = "\n".join(report_parts)
        logger.info("   -> Generated Surgical Context Report:\n%s", report)
        return report

    def _find_callers(self, symbol_name: str | None) -> list[dict]:
        """Finds all symbols in the graph that call the target symbol."""
        if not symbol_name:
            return []
        return [
            data
            for data in self.symbols.values()
            if symbol_name in data.get("calls", [])
        ]
