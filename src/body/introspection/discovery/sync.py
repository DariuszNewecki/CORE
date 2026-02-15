# src/features/introspection/discovery/sync.py

"""Refactored logic for src/features/introspection/discovery/sync.py."""

from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .semantics import _split_capability_key


# ID: 1124a2cb-cfaf-4a2f-82a7-3f4cfd171fd3
async def run_capability_upsert(db: AsyncSession, keys: set[str]) -> int:
    """Sync constitutional capabilities into DB with authority boundaries."""
    upserted = 0
    for key in keys:
        domain, namespace = _split_capability_key(key)
        title = key.replace(".", " ").replace("_", " ").title()

        stmt = text(
            """
            INSERT INTO core.capabilities
                (name, domain, subdomain, title, owner, status, tags, updated_at)
            VALUES
                (:name, :domain, :subdomain, :title, 'constitution', 'Active', :tags, NOW())
            ON CONFLICT (domain, name) DO UPDATE SET
                subdomain = EXCLUDED.subdomain,
                status = 'Active',
                updated_at = NOW()
        """
        )

        await db.execute(
            stmt,
            {
                "name": key,
                "domain": domain,
                "subdomain": namespace,
                "title": title,
                "tags": json.dumps(["constitutional"]),
            },
        )
        upserted += 1
    return upserted
