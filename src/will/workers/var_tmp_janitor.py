# src/will/workers/var_tmp_janitor.py
"""var/tmp Janitor Worker (ADR-117) — Phase 1, report-only.

`var/tmp/` is CORE's repo-internal ephemeral-scratch surface, and nothing reaps
it. This worker scans the surface and posts a Blackboard report of the stale
reap *candidates* (entries older than the retention threshold, excluding pinned
`.keep` entries). It DELETES NOTHING.

Phase 1 is deliberately non-destructive (ADR-117 D5, the report-first ramp): it
proves the age/boundary selection predicate against live state before any
destructive Phase-2 follow-up (`tmp.reap` atomic action) is wired. Deterministic,
no LLM, read-only — selection is a pure function so it is unit-testable without
the daemon.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

# ADR-117 D2/D3 — the rails, as governor-tunable dials.
RETENTION_DAYS: int = 7
MAX_REAP_PER_RUN: int = 200

_KEEP_MARKER = ".keep"
_TMP_RELPATH = ("var", "tmp")
_SECONDS_PER_DAY = 86400.0


@dataclass(frozen=True)
# ID: 6550a504-7a08-4aac-8040-84cbab31749f
class ReapCandidate:
    """A stale var/tmp entry selected for (eventual, Phase-2) reaping."""

    path: Path
    age_days: float
    size_bytes: int


# ID: 4f24868a-a592-49a1-aef3-3ac94d1e6b57
def find_reap_candidates(
    tmp_root: Path,
    *,
    now_ts: float,
    retention_days: int = RETENTION_DAYS,
) -> list[ReapCandidate]:
    """Select stale top-level entries under ``tmp_root`` (ADR-117 D2).

    An entry is a candidate iff its mtime is older than ``retention_days`` AND it
    is not pinned by a ``.keep`` marker. Entries whose mtime cannot be read are
    skipped (fail-closed). This is selection only — no deletion — so the
    predicate is a pure, testable function; Phase 1 merely reports the result.
    An absent or non-directory ``tmp_root`` yields an empty list, never an error.
    """
    if not tmp_root.is_dir():
        return []
    cutoff_seconds = retention_days * _SECONDS_PER_DAY
    candidates: list[ReapCandidate] = []
    for entry in sorted(tmp_root.iterdir()):
        if _is_pinned(entry):
            continue
        try:
            mtime = entry.stat().st_mtime
        except OSError:
            logger.warning(
                "var_tmp_janitor: cannot stat %s — skipping (fail-closed)", entry
            )
            continue
        age_seconds = now_ts - mtime
        if age_seconds <= cutoff_seconds:
            continue
        candidates.append(
            ReapCandidate(
                path=entry,
                age_days=age_seconds / _SECONDS_PER_DAY,
                size_bytes=_entry_size(entry),
            )
        )
    return candidates


def _is_pinned(entry: Path) -> bool:
    """ADR-117 D6 — a ``.keep`` entry, or a dir containing one, is never reaped."""
    if entry.name == _KEEP_MARKER:
        return True
    if entry.is_dir() and (entry / _KEEP_MARKER).exists():
        return True
    return False


def _entry_size(entry: Path) -> int:
    """Best-effort byte size of a file or directory tree (advisory, for reporting)."""
    try:
        if entry.is_file():
            return entry.stat().st_size
        return sum(p.stat().st_size for p in entry.rglob("*") if p.is_file())
    except OSError:
        return 0


def _count_entries(tmp_root: Path) -> int:
    """Total top-level entries under ``tmp_root`` (0 if absent)."""
    if not tmp_root.is_dir():
        return 0
    return sum(1 for _ in tmp_root.iterdir())


# ID: cf53fbdb-6508-40d4-9aa4-2cdfe509b67d
class VarTmpJanitorWorker(Worker):
    """ADR-117 Phase 1 — report-only janitor for the var/tmp ephemeral-scratch surface.

    Scans ``var/tmp/`` and posts a Blackboard report of the stale reap candidates.
    It deletes NOTHING: Phase 1 proves the selection predicate against live state
    before any destructive Phase-2 follow-up (ADR-117 D5). Classed ``governance``
    (a deterministic system-state reporter, like ``observer_worker``), not
    ``sensing`` — it is not an audit-rule sensor.
    """

    declaration_name = "var_tmp_janitor"

    def __init__(self) -> None:
        from shared.infrastructure.bootstrap_registry import BootstrapRegistry

        super().__init__()
        repo_root: Path = BootstrapRegistry.get_repo_path()
        self._tmp_root: Path = repo_root.joinpath(*_TMP_RELPATH)

    # ID: 20f804ec-8083-4beb-85f0-145eda4797b9
    async def run(self) -> None:
        """Scan var/tmp and report reap candidates — no deletion (ADR-117 D5 Phase 1)."""
        await self.post_heartbeat()

        candidates = find_reap_candidates(self._tmp_root, now_ts=time.time())
        total_entries = _count_entries(self._tmp_root)
        would_reap_this_run = min(len(candidates), MAX_REAP_PER_RUN)
        oldest_days = max((c.age_days for c in candidates), default=0.0)
        reclaimable_bytes = sum(c.size_bytes for c in candidates)

        await self.post_report(
            "var_tmp_janitor.scan",
            {
                "mode": "report-only",  # ADR-117 D5 Phase 1 — deletes nothing
                "tmp_root": str(self._tmp_root),
                "total_entries": total_entries,
                "retention_days": RETENTION_DAYS,
                "reap_candidates": len(candidates),
                "would_reap_this_run": would_reap_this_run,  # honors MAX_REAP_PER_RUN
                "max_reap_per_run": MAX_REAP_PER_RUN,
                "oldest_candidate_days": round(oldest_days, 1),
                "reclaimable_bytes": reclaimable_bytes,
                "sample": [c.path.name for c in candidates[:10]],
            },
        )
        logger.info(
            "var_tmp_janitor: %d/%d var/tmp entries are reap candidates (report-only)",
            len(candidates),
            total_entries,
        )
