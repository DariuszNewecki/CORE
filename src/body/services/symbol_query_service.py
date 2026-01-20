# src/body/services/symbol_query_service.py

"""
SymbolQueryService - Body layer service for symbol search and lookup.

Constitutional Compliance:
- Body layer service: Provides capability without making decisions
- Mind/Body/Will separation: Encapsulates symbol database access
- No direct database access in Will: Will queries symbols through this service
- Dependency injection: Takes AsyncSession, no global imports

Part of Mind-Body-Will architecture:
- Mind: Database contains Symbol definitions (what exists in codebase)
- Body: This service provides search/lookup capability
- Will: Uses this service to find symbols for decision-making (strategy)
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database.models import Symbol
from shared.logger import getLogger


logger = getLogger(__name__)

__all__ = ["SymbolQueryService"]


# ID: f6789012-3456-7890-abcd-ef1234567890
class SymbolQueryService:
    """
    Body service for symbol search and lookup operations.

    Responsibilities:
    - Provide search interface for symbols by name, module, qualname
    - Encapsulate symbol database queries
    - Return structured symbol data for Will to use in decisions

    Does NOT:
    - Decide which symbols to use (that's Will)
    - Modify symbols (that's SymbolDefinitionRepository)
    - Generate symbols (that's code analysis tools)
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize service with database session.

        Args:
            session: Active database session for queries
        """
        self.session = session

    # ID: 01234567-89ab-cdef-0123-456789abcdef
    async def search_symbols(
        self, query: str, limit: int | None = None
    ) -> list[Symbol]:
        """
        Search symbols by name or module using fuzzy matching.

        Args:
            query: Search term (matched against qualname and module)
            limit: Optional maximum number of results

        Returns:
            List of Symbol instances matching the query

        Constitutional Note:
        This is a read operation. Will uses this to discover available symbols
        for import generation or code understanding.

        Example:
            symbols = await symbol_service.search_symbols("FileHandler")
        """
        # Clean query for SQL ILIKE
        clean_query = query.strip()

        stmt = select(Symbol).where(
            or_(
                Symbol.qualname.ilike(f"%{clean_query}%"),
                Symbol.module.ilike(f"%{clean_query}%"),
            )
        )

        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        symbols = list(result.scalars().all())

        logger.debug("Symbol search for '%s' returned %d results", query, len(symbols))
        return symbols

    # ID: 12345678-9abc-def0-1234-56789abcdef0
    async def find_by_name(self, name: str) -> Symbol | None:
        """
        Find symbol by exact name match.

        Args:
            name: Exact symbol name to find

        Returns:
            Symbol instance if found, None otherwise

        Constitutional Note:
        Exact lookup for when Will knows precisely which symbol it needs.
        Returns single result or None (not a list).

        Example:
            symbol = await symbol_service.find_by_name("FileHandler")
        """
        stmt = select(Symbol).where(Symbol.name == name).limit(1)

        result = await self.session.execute(stmt)
        symbol = result.scalar_one_or_none()

        if symbol:
            logger.debug("Found symbol: %s in %s", name, symbol.module)
        else:
            logger.debug("Symbol not found: %s", name)

        return symbol

    # ID: 23456789-abcd-ef01-2345-6789abcdef01
    async def find_by_module(self, module: str) -> list[Symbol]:
        """
        Find all symbols in a specific module.

        Args:
            module: Module path (e.g., "shared.infrastructure.database")

        Returns:
            List of Symbol instances in the module

        Constitutional Note:
        Module-level queries for when Will needs to understand
        what's available in a specific module.

        Example:
            symbols = await symbol_service.find_by_module("src.body.services")
        """
        stmt = select(Symbol).where(Symbol.module == module)

        result = await self.session.execute(stmt)
        symbols = list(result.scalars().all())

        logger.debug("Found %d symbols in module %s", len(symbols), module)
        return symbols

    # ID: 3456789a-bcde-f012-3456-789abcdef012
    async def find_by_qualname(self, qualname: str) -> Symbol | None:
        """
        Find symbol by fully qualified name.

        Args:
            qualname: Fully qualified name (e.g., "FileHandler.write_file")

        Returns:
            Symbol instance if found, None otherwise

        Constitutional Note:
        Most precise lookup method. Will uses this when it has
        the complete qualified path to a symbol.

        Example:
            symbol = await symbol_service.find_by_qualname(
                "shared.infrastructure.storage.FileHandler.write_file"
            )
        """
        stmt = select(Symbol).where(Symbol.qualname == qualname).limit(1)

        result = await self.session.execute(stmt)
        symbol = result.scalar_one_or_none()

        if symbol:
            logger.debug("Found symbol by qualname: %s", qualname)
        else:
            logger.debug("Symbol not found by qualname: %s", qualname)

        return symbol

    # ID: 456789ab-cdef-0123-4567-89abcdef0123
    async def get_symbols_by_file(self, file_path: str) -> list[Symbol]:
        """
        Get all symbols defined in a specific file.

        Args:
            file_path: Repository-relative file path

        Returns:
            List of Symbol instances defined in the file

        Constitutional Note:
        File-level queries for when Will needs to understand
        what's defined in a specific source file.

        Example:
            symbols = await symbol_service.get_symbols_by_file(
                "src/body/services/mind_state_service.py"
            )
        """
        stmt = select(Symbol).where(Symbol.file_path == file_path)

        result = await self.session.execute(stmt)
        symbols = list(result.scalars().all())

        logger.debug("Found %d symbols in file %s", len(symbols), file_path)
        return symbols


# Constitutional Note:
# This service exists because Will layer MUST NOT import get_session directly.
# Symbol queries are reads, but they're still infrastructure access.
# Will depends on Body for capabilities. This service IS that capability.
# Any Will component needing symbol data should receive SymbolQueryService via DI.
