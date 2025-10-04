# src/services/repositories/db/status_service.py
"""
Provides functionality for the status module.
"""

from __future__ import annotations

import asyncio

import typer

from services.repositories.db.common import (
    ensure_ledger,
    get_applied,
    load_policy,
)

# <-- CORRECTED IMPORT
from services.repositories.db.engine import ping


# ID: 75fac84c-5818-47c0-9d50-c0670d065c8c
def status() -> None:
    """Show DB connectivity and migration status."""

    async def _run():
        # 1) connection/ping
        try:
            info = await ping()
            typer.echo(f"✅ Connected: {info['version']}")
        except Exception as e:
            typer.echo(f"❌ Connection failed: {e}", err=True)
            raise

        # 2) policy & migrations
        pol = load_policy()
        order = pol.get("migrations", {}).get("order", [])

        await ensure_ledger()
        applied = await get_applied()
        pending = [m for m in order if m not in applied]

        typer.echo(f"Applied: {sorted(list(applied)) or '—'}")
        typer.echo(f"Pending: {pending or '—'}")

    asyncio.run(_run())
