# src/will/tools/context/retriever.py

"""
Context retrieval orchestration for code generation.
"""

from __future__ import annotations

import re
from pathlib import Path

from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger

from .code_snippet_extractor import CodeSnippetExtractor
from .embedding_search import EmbeddingSearchService
from .models import CodeExample
from .query_builder import SymbolQueryBuilder


logger = getLogger(__name__)


# ID: ee1dc1a7-5076-4c65-afe2-3abe6ab52280
class ContextRetriever:
    """
    Orchestrates retrieval of code context for AI-driven code generation.

    Coordinates embedding search, database queries, and snippet extraction.
    """

    def __init__(self, repo_root: Path, cog, qdrant):
        self.repo_root = repo_root
        self.search = EmbeddingSearchService(cog, qdrant)
        self.snippet_extractor = CodeSnippetExtractor(repo_root)
        self.query_builder = SymbolQueryBuilder()

    # ID: 16312ff7-2d23-49b2-9f18-44580f40032f
    async def read_target_file(self, goal: str) -> tuple[str | None, str | None]:
        """
        Extract and read target file path from goal string.

        Args:
            goal: Goal string containing "for src/path/to/file.py"

        Returns:
            Tuple of (file_content, file_path) or (None, None)
        """
        match = re.search(r"for\s+(src/[^\s]+\.py)", goal)
        if not match:
            return None, None

        file_path = match.group(1)
        content = await self.snippet_extractor.read_file(file_path)

        return content, file_path if content else (None, None)

    # ID: 639643e0-8ec2-4db5-a592-d75a7082f5e0
    async def find_examples(self, goal: str, layer: str) -> list[CodeExample]:
        """
        Find relevant code examples from a specific architectural layer.

        Args:
            goal: Description of what code to find
            layer: Architectural layer to search in

        Returns:
            List of CodeExample objects with snippets and metadata
        """
        # Search for relevant symbols
        hits = await self.search.search_by_layer(goal, layer, limit=10)
        if not hits:
            return []

        symbol_ids = self.search.extract_symbol_ids(hits)
        if not symbol_ids:
            return []

        # Fetch symbol metadata from database
        symbol_data = await self._fetch_symbol_data(symbol_ids)

        # Build code examples with snippets
        examples = await self._build_examples(symbol_data)

        return examples

    async def _fetch_symbol_data(self, symbol_ids: list[str]) -> list:
        """Fetch symbol metadata from database."""
        query, params = self.query_builder.build_symbols_by_ids_query(symbol_ids)

        async with get_session() as session:
            result = await session.execute(query, params)
            return result.fetchall()

    async def _build_examples(self, symbol_rows) -> list[CodeExample]:
        """Build CodeExample objects from database rows with code snippets."""
        examples = []

        for row in symbol_rows:
            snippet = await self.snippet_extractor.extract_snippet(
                file_path=row.file_path,
                line_number=row.line_number,
                context_lines=20,
            )

            if snippet is None:
                continue

            examples.append(
                CodeExample(
                    file_path=row.file_path,
                    qualname=row.qualname,
                    snippet=snippet,
                    docstring=row.docstring[:100] if row.docstring else "",
                    score=0.0,
                )
            )

        return examples
