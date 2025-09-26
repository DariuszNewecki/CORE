# src/agents/reconnaissance_agent.py
"""
Implements the ReconnaissanceAgent, a non-LLM agent that performs targeted
queries against the knowledge graph to build a minimal, surgical context for the Planner.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from shared.logger import getLogger

log = getLogger("recon_agent")

SYMBOL_REGEX = re.compile(r"\b([A-Z][A-Za-z0-9_]+|`[a-zA-Z0-9_./]+`)\b")


# ID: f2d9b442-6f3f-4a62-978c-6d5fb9c20b1d
class ReconnaissanceAgent:
    """Queries the knowledge graph to build a focused context for a task."""

    def __init__(self, knowledge_graph: Dict[str, Any]):
        """Initializes with the full knowledge graph."""
        self.graph = knowledge_graph
        self.symbols = knowledge_graph.get("symbols", {})

    # ID: f3952e9d-1228-4013-9bc8-91d0b551d3b2
    def generate_report(self, goal: str) -> str:
        """
        Analyzes a goal, queries the graph, and generates a surgical context report.
        """
        log.info(f"🔬 Conducting reconnaissance for goal: '{goal}'")

        target_symbols = [s.replace("`", "") for s in SYMBOL_REGEX.findall(goal)]
        log.info(f"   -> Identified target symbols: {target_symbols}")

        if not target_symbols:
            return (
                "# Reconnaissance Report\n\n- No specific code symbols were "
                "identified in the goal."
            )

        report_parts = ["# Reconnaissance Report\n"]
        for symbol_name in target_symbols:
            symbol_data = self._find_symbol_data(symbol_name)
            if not symbol_data:
                report_parts.append(
                    f"\n## Symbol: `{symbol_name}`\n\n- **Status:** Not found "
                    "in the Knowledge Graph."
                )
                continue

            callers = self._find_callers(symbol_name)

            report_parts.append(f"\n## Symbol: `{symbol_data['key']}`")
            report_parts.append(f"- **Type:** {symbol_data['type']}")
            report_parts.append(f"- **Location:** `{symbol_data['file']}`")
            report_parts.append(f"- **Intent:** {symbol_data['intent']}")

            if callers:
                report_parts.append("- **Referenced By:**")
                for caller in callers:
                    report_parts.append(f"  - `{caller['key']}`")
            else:
                report_parts.append(
                    "- **Referenced By:** None. This symbol appears to be "
                    "unreferenced."
                )

        report_parts.append(
            "\n---\n**Conclusion:** The analysis is complete. Use this "
            "information to form a precise plan."
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
