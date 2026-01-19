# src/features/introspection/vectorization/db_queries.py

"""Database interactions for symbol vectorization."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 59968999-9b48-474d-8fb7-33772cc8c8e5
async def fetch_initial_state(
    session: AsyncSession,
) -> tuple[list[dict], dict[str, str]]:
    """Fetch symbols and existing links in parallel."""
    stmt_syms = text(
        """
        SELECT id, symbol_path, module, fingerprint AS structural_hash
        FROM core.symbols WHERE is_public = TRUE
    """
    )
    stmt_links = text("SELECT symbol_id, vector_id FROM core.symbol_vector_links")

    res_syms = await session.execute(stmt_syms)
    res_links = await session.execute(stmt_links)

    symbols = [dict(row._mapping) for row in res_syms]
    links = {str(row.symbol_id): str(row.vector_id) for row in res_links}
    return symbols, links


# ID: 8264af7b-d9d2-4033-8a6a-0b67f319bc9c
async def finalize_vector_update(session: AsyncSession, updates: list[dict]):
    """Update links and set last_embedded timestamps."""
    if not updates:
        return

    # 1. Update links
    await session.execute(
        text(
            """
        INSERT INTO core.symbol_vector_links (symbol_id, vector_id, embedding_model, embedding_version, created_at)
        VALUES (:symbol_id, :vector_id, :embedding_model, :embedding_version, NOW())
        ON CONFLICT (symbol_id) DO UPDATE SET
            vector_id = EXCLUDED.vector_id,
            created_at = NOW();
    """
        ),
        updates,
    )

    # 2. Update symbols
    await session.execute(
        text(
            "UPDATE core.symbols SET last_embedded = NOW() WHERE id = ANY(:symbol_ids)"
        ),
        {"symbol_ids": [u["symbol_id"] for u in updates]},
    )
    logger.info("Updated %d DB records.", len(updates))
