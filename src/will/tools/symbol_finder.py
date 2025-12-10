# src/will/tools/symbol_finder.py
"""
Symbol Finder Tool.

Allows agents to locate symbols (classes, functions) within the codebase
by querying the Knowledge Graph database (SSOT).

Use cases:
- Resolving ImportErrors (finding the correct module for a class).
- Discovery (finding existing tools or helpers).

Constitutional Alignment:
- data_governance: Reads from DB, does not scan filesystem.
- clarity_first: Returns structured, actionable import paths.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import or_, select

from shared.infrastructure.database.models import Symbol
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)


@dataclass
# ID: 4793d66d-2e97-4e8d-9e5c-07d54788047b
class SymbolLocation:
    """Structured location data for a symbol."""

    name: str
    module: str
    qualname: str
    file_path: str

    @property
    # ID: 090a832e-2ef6-481c-b6ca-cfa74c5f4768
    def import_statement(self) -> str:
        """Generates a valid python import statement."""
        return f"from {self.module} import {self.name}"


# ID: fedf6722-d4e6-424c-b411-18a2bb15c611
class SymbolFinder:
    """
    Tool for locating code symbols in the persistent Knowledge Graph.
    """

    # ID: bd03a7ea-b4d2-4f32-a2e9-8130887c833b
    async def find_symbol(self, query: str, limit: int = 5) -> list[SymbolLocation]:
        """
        Search for a symbol by name (case-insensitive substring).
        """
        # Clean the query: remove quotes, parens, and trailing punctuation
        clean_query = query.strip(" \"'(),.")
        if not clean_query or len(clean_query) < 3:
            return []

        logger.debug("SymbolFinder: Searching for '%s'", clean_query)

        async with get_session() as session:
            # Search against qualname (e.g. "ActionHandler") and module path
            stmt = (
                select(Symbol)
                .where(
                    or_(
                        Symbol.qualname.ilike(f"%{clean_query}%"),
                        Symbol.module.ilike(f"%{clean_query}%"),
                    )
                )
                .limit(limit)
            )

            result = await session.execute(stmt)
            rows = result.scalars().all()

            locations = []
            for row in rows:
                simple_name = row.qualname.split(".")[-1]
                file_path = f"{row.module.replace('.', '/')}.py"

                loc = SymbolLocation(
                    name=simple_name,
                    module=row.module,
                    qualname=row.qualname,
                    file_path=file_path,
                )
                locations.append(loc)

            # Sort results: Exact name matches first, then shortest import paths
            locations.sort(
                key=lambda x: (x.name.lower() != clean_query.lower(), len(x.module))
            )

            if locations:
                logger.info(
                    f"SymbolFinder: Found {len(locations)} matches for '{clean_query}'"
                )
            else:
                logger.debug("SymbolFinder: No matches found for '%s'", clean_query)

            return locations

    # ID: 0e8f6439-eef6-469a-9099-9be043f6e30a
    async def get_context_for_import_error(self, text: str) -> str:
        """
        Helper specifically for agents fixing ImportErrors.
        Parses a failed import line OR error message and suggests corrections.
        """
        targets = set()

        # 1. Parse ModuleNotFoundError: No module named 'src.body.action_handler'
        # We split the path and search for the last segment (the specific file or module attempted)
        if "No module named" in text:
            match = re.search(r"No module named ['\"]([^'\"]+)['\"]", text)
            if match:
                full_path = match.group(1)
                parts = full_path.split(".")
                # Add the last part (likely the file/module name)
                targets.add(parts[-1])

        # 2. Parse ImportError: cannot import name 'ActionHandler' from 'src.body'
        elif "cannot import name" in text:
            match = re.search(r"cannot import name ['\"]([^'\"]+)['\"]", text)
            if match:
                targets.add(match.group(1))

        # 3. Fallback: Tokenize and heuristics
        else:
            # Remove python keywords and common punctuation
            clean = text.replace("from", "").replace("import", "").replace(",", " ")
            parts = clean.split()
            for part in parts:
                # Clean up potential code bits
                candidate = part.strip(" \"'(),.:")
                # Heuristic: CamelCase or snake_case_with_length might be symbols
                if candidate and len(candidate) > 3 and not candidate.startswith("_"):
                    # Ignore obvious error words
                    if candidate.lower() not in {
                        "error",
                        "module",
                        "traceback",
                        "line",
                        "file",
                    }:
                        targets.add(candidate)

        suggestions = []
        for target in targets:
            matches = await self.find_symbol(target, limit=3)
            if matches:
                suggestions.append(f"Could not find '{target}'. Did you mean:")
                for m in matches:
                    suggestions.append(
                        f"  - {m.import_statement} (Defined in: {m.file_path})"
                    )

        if not suggestions:
            return ""

        return "\n".join(suggestions)
