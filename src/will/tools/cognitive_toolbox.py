# src/will/tools/cognitive_toolbox.py

"""
Cognitive Toolbox - Surgical RAG Implementation.
Provides governed access to specific code logic based on Agent requests.
"""

from __future__ import annotations

from shared.context import CoreContext
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: cd3102e3-b2de-4669-b36f-229d1f791028
class CognitiveToolbox:
    def __init__(self, context: CoreContext):
        self.context = context
        self.knowledge_service = KnowledgeService(context.git_service.repo_path)

    # ID: a531830c-e57d-4762-9a19-13a4939f2441
    async def search_vectors(self, query: str, limit: int = 5) -> list[dict]:
        """Fuzzy semantic search via Qdrant."""
        cognitive = await self.context.registry.get_cognitive_service()
        return await cognitive.search_capabilities(query, limit=limit)

    # ID: fd58c351-8b10-4584-aadc-6ecabd37127c
    async def lookup_symbol(self, qualname: str) -> dict | None:
        """Strict lookup via Postgres Knowledge Graph."""
        graph = await self.knowledge_service.get_graph()
        for key, data in graph.get("symbols", {}).items():
            if data.get("qualname") == qualname or key.endswith(f"::{qualname}"):
                return data
        return None

    # ID: 558ecc70-5a37-4ba9-9d5b-396fdc9eb8d5
    async def read_file_content(self, rel_path: str) -> str:
        """Governed file read via repo_path."""
        path_str = str(rel_path).lstrip("/")
        abs_path = self.context.git_service.repo_path / path_str
        if abs_path.exists() and abs_path.is_file():
            return abs_path.read_text(encoding="utf-8")
        logger.warning("Toolbox: File not found at %s", abs_path)
        return f"Error: File {rel_path} not found."
