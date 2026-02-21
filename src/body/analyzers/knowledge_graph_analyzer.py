# src/body/analyzers/knowledge_graph_analyzer.py
# ID: b64ba9c9-f55c-4a24-bc2d-d8c2fa04b43e

"""
Knowledge Graph Analyzer - PARSE Phase Component.
Standardized interface for system introspection.

Constitutional Alignment:
- Phase: PARSE (Structural analysis)
- Authority: CODE (Implementation)
- Boundary: Requires repo_root via dependency injection (no settings fallback)
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from body.analyzers.base_analyzer import BaseAnalyzer
from body.introspection.knowledge_graph_service import KnowledgeGraphBuilder
from shared.component_primitive import ComponentResult  # Component, ComponentPhase,
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: e9b2c3d4-f5a6-7b8c-9d0e-1f2a3b4c5d6e
class KnowledgeGraphAnalyzer(BaseAnalyzer):
    """
    Standardized component for building the Knowledge Graph.

    Constitutional Requirement:
    - MUST receive repo_root parameter (no settings fallback)
    - Body layer components do not access settings directly
    """

    # ID: 46b5ce81-b2fc-4822-88ba-53682cf1f431
    async def execute(
        self, repo_root: Path | None = None, **kwargs: Any
    ) -> ComponentResult:
        """
        Execute the codebase scan.

        Args:
            repo_root: Repository root path (required for constitutional compliance)

        Constitutional Compliance:
        - Requires repo_root parameter (no settings fallback)
        - Returns error if repo_root not provided (fail fast, dependency injection enforced)
        """
        start_time = time.time()

        # Constitutional boundary enforcement: Body requires proper parameters
        if repo_root is None:
            return ComponentResult(
                component_id=self.component_id,
                ok=False,
                data={
                    "error": "KnowledgeGraphAnalyzer requires repo_root parameter. "
                    "Body layer components must not access settings directly."
                },
                phase=self.phase,
                confidence=0.0,
            )

        # Instantiate the pure logic builder
        builder = KnowledgeGraphBuilder(repo_root)

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
                "repo_root": str(repo_root),
            },
            duration_sec=duration,
        )
