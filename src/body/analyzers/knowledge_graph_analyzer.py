# src/body/analyzers/knowledge_graph_analyzer.py
# ID: b64ba9c9-f55c-4a24-bc2d-d8c2fa04b43e

"""
Knowledge Graph Analyzer - PARSE Phase Component.
Standardized interface for system introspection.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from features.introspection.knowledge_graph_service import KnowledgeGraphBuilder
from shared.component_primitive import Component, ComponentPhase, ComponentResult
from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: e9b2c3d4-f5a6-7b8c-9d0e-1f2a3b4c5d6e
class KnowledgeGraphAnalyzer(Component):
    """
    Standardized component for building the Knowledge Graph.
    """

    @property
    # ID: 6558f4df-41c6-4e34-9b24-713a12c1b549
    def phase(self) -> ComponentPhase:
        return ComponentPhase.PARSE

    # ID: 46b5ce81-b2fc-4822-88ba-53682cf1f431
    async def execute(
        self, repo_root: Path | None = None, **kwargs: Any
    ) -> ComponentResult:
        """
        Execute the codebase scan.
        """
        start_time = time.time()
        root = repo_root or settings.REPO_PATH

        # Instantiate the pure logic builder
        builder = KnowledgeGraphBuilder(root)

        # Build the graph (pure in-memory operation)
        graph_data = builder.build()

        duration = time.time() - start_time

        return ComponentResult(
            component_id=self.component_id,
            ok=True,
            data=graph_data,
            phase=self.phase,
            confidence=1.0,
            metadata={
                "symbol_count": graph_data["metadata"].get("symbol_count", 0),
                "repo_root": str(root),
            },
            duration_sec=duration,
        )
