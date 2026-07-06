# src/body/introspection/drift_service.py
"""
Symbols-drift service — ADR-143 D3b.

Compares the source-side symbol inventory (# ID: anchors extracted by
IdAnchorScanner) against the runtime symbol graph (core.symbols rows) to
produce a staleness report with three categories:

  unregistered  — in source, not in graph (DbSyncWorker hasn't picked it up yet)
  phantom       — in graph, not in source (symbol deleted; graph entry persists)
  anchor_missing — public def/class in source with no # ID: anchor (governance deficit)

Both sets are matched on symbol_path ("{rel_path}::{bare_name}"), which is
the canonical link between source and core.symbols.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from body.introspection.id_anchor_scanner import scan
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)

_SAMPLE_CAP = 50


# ID: 51f59218-c7f5-41ae-b2c9-87d4459e14d2
async def run_drift_analysis_async(root: Path) -> dict:
    """Return a symbols-drift snapshot for /v1/status/drift?scope=symbols.

    Opens its own DB session so callers need no session plumbing.
    The filesystem walk covers src/ only (~100 files, < 200 ms).
    """
    # 1. Source-side: all # ID: anchored public symbols + those missing anchors.
    scan_result = scan(root)
    source_paths = frozenset(s.symbol_path for s in scan_result.anchored)

    # 2. Graph-side: all non-deprecated symbols whose file lives under src/.
    graph_paths: frozenset[str] = frozenset()
    try:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT symbol_path
                    FROM core.symbols
                    WHERE file_path LIKE 'src/%.py'
                      AND definition_status != 'deprecated'
                    """
                )
            )
            graph_paths = frozenset(row[0] for row in result if row[0])
    except Exception as exc:
        logger.warning("drift_service: DB query failed — graph-side empty: %s", exc)

    # 3. Symmetric diff.
    unregistered = sorted(source_paths - graph_paths)
    phantom = sorted(graph_paths - source_paths)
    anchor_missing = sorted(scan_result.anchor_missing)

    return {
        "available": True,
        "unregistered_count": len(unregistered),
        "phantom_count": len(phantom),
        "anchor_missing_count": len(anchor_missing),
        "unregistered": unregistered[:_SAMPLE_CAP],
        "phantom": phantom[:_SAMPLE_CAP],
        "anchor_missing": anchor_missing[:_SAMPLE_CAP],
        "sample_cap": _SAMPLE_CAP,
    }
