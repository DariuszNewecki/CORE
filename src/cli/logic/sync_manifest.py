# src/body/cli/logic/sync_manifest.py
# ID: 7d59507f-ddd3-4eb6-ba8d-22598dc9bbfd
"""
LEGACY / DEPRECATED — DO NOT USE.

This module previously synchronized a legacy project manifest under `.intent/`.
That behavior is constitutionally invalid:

- `.intent/` is READ-ONLY for BODY.
"""

from __future__ import annotations

import typer

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: fd8e5164-0a37-45e7-8701-7a1935d99d88
async def sync_manifest() -> None:
    """
    Disabled operation: BODY may not write to `.intent/`.
    """
    logger.error(
        "sync-manifest is deprecated and disabled: "
        "BODY may not write to `.intent/`. "
        "Migrate any consumers to SSOT (Postgres)."
    )
    raise typer.Exit(code=1)
