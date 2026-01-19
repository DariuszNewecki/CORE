# src/features/introspection/sync/engine.py

"""Refactored logic for src/features/introspection/sync/engine.py."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ID: 1d4f3f97-e8ce-4ebc-82b4-2d7f41ba55dd
async def run_db_merge(session: AsyncSession, code_state: list[dict]) -> dict[str, int]:
    """Executes the set-based merge logic exactly as in the original file."""
    stats = {"scanned": len(code_state), "inserted": 0, "updated": 0, "deleted": 0}

    await session.execute(
        text(
            """
        CREATE TEMPORARY TABLE core_symbols_staging (LIKE core.symbols INCLUDING DEFAULTS) ON COMMIT DROP;
    """
        )
    )

    if code_state:
        await session.execute(
            text(
                """
            INSERT INTO core_symbols_staging (id, symbol_path, module, qualname, kind, ast_signature, fingerprint, state, is_public, calls, domain)
            VALUES (:id, :symbol_path, :module, :qualname, :kind, :ast_signature, :fingerprint, :state, :is_public, :calls, :domain)
        """
            ),
            code_state,
        )

    # 1. Calculate Deleted
    stats["deleted"] = (
        await session.execute(
            text(
                "SELECT COUNT(*) FROM core.symbols WHERE symbol_path NOT IN (SELECT symbol_path FROM core_symbols_staging)"
            )
        )
    ).scalar_one()
    # 2. Calculate Inserted
    stats["inserted"] = (
        await session.execute(
            text(
                "SELECT COUNT(*) FROM core_symbols_staging WHERE symbol_path NOT IN (SELECT symbol_path FROM core.symbols)"
            )
        )
    ).scalar_one()
    # 3. Calculate Updated
    stats["updated"] = (
        await session.execute(
            text(
                """
        SELECT COUNT(*) FROM core.symbols s JOIN core_symbols_staging st ON s.symbol_path = st.symbol_path
        WHERE s.fingerprint != st.fingerprint OR s.calls::text != st.calls::text OR s.domain != st.domain
    """
            )
        )
    ).scalar_one()

    # Apply Operations
    await session.execute(
        text(
            "DELETE FROM core.symbols WHERE symbol_path NOT IN (SELECT symbol_path FROM core_symbols_staging)"
        )
    )

    await session.execute(
        text(
            """
        UPDATE core.symbols
        SET fingerprint = st.fingerprint, calls = st.calls, domain = st.domain,
            last_modified = NOW(), last_embedded = NULL, updated_at = NOW()
        FROM core_symbols_staging st WHERE core.symbols.symbol_path = st.symbol_path
        AND (core.symbols.fingerprint != st.fingerprint OR core.symbols.calls::text != st.calls::text OR core.symbols.domain != st.domain);
    """
        )
    )

    await session.execute(
        text(
            """
        INSERT INTO core.symbols (id, symbol_path, module, qualname, kind, ast_signature, fingerprint, state, is_public, calls, domain, created_at, updated_at, last_modified, first_seen, last_seen)
        SELECT id, symbol_path, module, qualname, kind, ast_signature, fingerprint, state, is_public, calls, domain, NOW(), NOW(), NOW(), NOW(), NOW()
        FROM core_symbols_staging ON CONFLICT (symbol_path) DO NOTHING;
    """
        )
    )

    return stats
