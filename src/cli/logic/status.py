# src/cli/commands/status.py
"""
CLI command to check database connectivity and migration status.
"""
from __future__ import annotations

import asyncio

import typer

# --- THIS IS THE FIX ---
# It now imports from the correct 'services' layer, not the 'cli' layer.
from services.repositories.db.common import (
    ensure_ledger,
    get_applied,
    load_policy,
)
from services.repositories.db.engine import ping


# ID: 10235f65-fae8-473a-8a60-f65711b87f43
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
