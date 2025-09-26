# src/core/agents/reconnaissance_agent.py
"""
Implements the ReconnaissanceAgent, which performs targeted queries and semantic
search against the knowledge graph to build a minimal, surgical context for the Planner.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from core.cognitive_service import CognitiveService
from shared.logger import getLogger

log = getLogger("recon_agent")

SYMBOL_REGEX = re.compile(r"\b([A-Z][A-Za-z0-9_]+|`[a-zA-Z0-9_./]+`)\b")


# ID: f2d9b442-6f3f-4a62-978c-6d5fb9c20b1d
class ReconnaissanceAgent:
    """Queries the knowledge graph to build a focused context for a task."""

    def __init__(
        self, knowledge_graph: Dict[str, Any], cognitive_service: CognitiveService
    ):
        """Initializes with the knowledge graph and cognitive service for search."""
        self.graph = knowledge_graph
        self.symbols = knowledge_graph.get("symbols", {})
        self.cognitive_service = cognitive_service

    async def _find_relevant_files(self, goal: str) -> List[str]:
        """Performs a semantic search to find files relevant to the goal."""
        log.info("   -> Performing semantic search for relevant files...")
        try:
            search_results = await self.cognitive_service.search_capabilities(
                goal, limit=3
            )
            if not search_results:
                return []

            relevant_files = set()
            for hit in search_results:
                if (payload := hit.get("payload")) and (
                    file_path := payload.get("source_path")
                ):
                    relevant_files.add(file_path)

            log.info(f"   -> Found relevant files: {list(relevant_files)}")
            return sorted(list(relevant_files))
        except Exception as e:
            log.warning(f"Semantic file search failed: {e}")
            return []

    # ID: f3952e9d-1228-4013-9bc8-91d0b551d3b2
    async def generate_report(self, goal: str) -> str:
        """
        Analyzes a goal, queries the graph, and generates a surgical context report.
        """
        log.info(f"🔬 Conducting reconnaissance for goal: '{goal}'")

        # Perform both symbol-based and semantic search for comprehensive context
        target_symbols = [s.replace("`", "") for s in SYMBOL_REGEX.findall(goal)]
        relevant_files = await self._find_relevant_files(goal)

        log.info(f"   -> Identified target symbols: {target_symbols}")

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
                "\n- No specific code symbols were identified in the goal."
            )
        else:
            for symbol_name in target_symbols:
                symbol_data = self._find_symbol_data(symbol_name)
                if not symbol_data:
                    report_parts.append(
                        f"\n## Symbol: `{symbol_name}`\n\n- **Status:** Not found in the Knowledge Graph."
                    )
                    continue

                callers = self._find_callers(symbol_name)
                report_parts.append(
                    f"\n## Symbol: `{symbol_data.get('key', symbol_name)}`"
                )
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
        log.info(f"   -> Generated Surgical Context Report:\n{report}")
        return report

    def _find_symbol_data(self, symbol_name: str) -> Dict | None:
        """Finds the main data entry for a symbol by name or key."""
        for key, data in self.symbols.items():
            if key.endswith(f"::{symbol_name}") or data.get("name") == symbol_name:
                return data
        return None

    def _find_callers(self, symbol_name: str) -> List[Dict]:
        """Finds all symbols in the graph that call the target symbol."""
        return [
            data
            for data in self.symbols.values()
            if symbol_name in data.get("calls", [])
        ]
