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
# ID: 914986d3-5c26-4013-bb01-a50be3d3e3b8
class SymbolLocation:
    """Structured location data for a symbol."""

    name: str
    module: str
    qualname: str
    file_path: str

    @property
    # ID: b689930f-3484-4050-8bab-b09405aec400
    def import_statement(self) -> str:
        """Generates a valid python import statement."""
        return f"from {self.module} import {self.name}"


# ID: c7bd3d61-dbc0-4b04-b74c-85c8eb1fc924
class SymbolFinder:
    """
    Tool for locating code symbols in the persistent Knowledge Graph.
    """

    # ID: aaf5c18c-346e-4623-b948-38e13aed8000
    async def find_symbol(self, query: str, limit: int = 5) -> list[SymbolLocation]:
        """
        Search for a symbol by name (case-insensitive substring).
        """
        clean_query = query.strip(" \"'(),.")
        if not clean_query or len(clean_query) < 3:
            return []
        logger.debug("SymbolFinder: Searching for '%s'", clean_query)
        async with get_session() as session:
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
            locations.sort(
                key=lambda x: (x.name.lower() != clean_query.lower(), len(x.module))
            )
            if locations:
                logger.info(
                    "SymbolFinder: Found %s matches for '%s'",
                    len(locations),
                    clean_query,
                )
            else:
                logger.debug("SymbolFinder: No matches found for '%s'", clean_query)
            return locations

    # ID: 39b8642a-64fd-49ad-b8c1-e8496aa9a04e
    async def get_context_for_import_error(self, text: str) -> str:
        """
        Helper specifically for agents fixing ImportErrors.
        Parses a failed import line OR error message and suggests corrections.
        """
        targets = set()
        if "No module named" in text:
            match = re.search("No module named ['\\\"]([^'\\\"]+)['\\\"]", text)
            if match:
                full_path = match.group(1)
                parts = full_path.split(".")
                targets.add(parts[-1])
        elif "cannot import name" in text:
            match = re.search("cannot import name ['\\\"]([^'\\\"]+)['\\\"]", text)
            if match:
                targets.add(match.group(1))
        else:
            clean = text.replace("from", "").replace("import", "").replace(",", " ")
            parts = clean.split()
            for part in parts:
                candidate = part.strip(" \"'(),.:")
                if candidate and len(candidate) > 3 and (not candidate.startswith("_")):
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
