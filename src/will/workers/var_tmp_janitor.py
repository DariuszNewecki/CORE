# src/will/workers/var_tmp_janitor.py
"""var/tmp Janitor Worker (ADR-117) — Phase 2, reaping.

`var/tmp/` is CORE's repo-internal ephemeral-scratch surface. This worker scans
the surface, selects the stale reap candidates (top-level entries older than the
retention threshold, excluding pinned `.keep` entries), deletes up to
`MAX_REAP_PER_RUN` of them, and posts a Blackboard report of what it removed.

Phase 1 ran report-only to prove the age/boundary predicate against live state
(ADR-117 D5). Phase 2 deletes through Body's `FileService` — the FileHandler
chokepoint, where `var/tmp/` classifies as `ephemeral-scratch` — matching the
`canary_janitor` precedent (ADR-147, #772) rather than a `dangerous`-impact
`tmp.reap` atomic action: a worker-invoked dangerous action would bypass the
proposal approval layer that gives that classification its meaning (#633).
See the ADR-117 amendment (2026-10-06).

Rails (ADR-117 D2/D3/D6): age floor, per-run cap, every target's resolved path
must sit directly under `var/tmp/`, symlinks are never followed or removed,
`var/tmp/` itself is never deleted, `.keep` pins an entry. Deterministic, no LLM.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from body.services.file_service import FileService
from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

# ADR-117 D2/D3 — the rails, as governor-tunable dials. Governed via
# operational_config.yaml workers.var_tmp_janitor (#774, ADR-040 sweep);
# these module constants are now thin governed aliases, not literals.
_CFG = load_operational_config().workers.var_tmp_janitor
RETENTION_DAYS: int = _CFG.retention_days
MAX_REAP_PER_RUN: int = _CFG.max_reap_per_run

_KEEP_MARKER = ".keep"
_TMP_RELPATH = ("var", "tmp")
_SECONDS_PER_DAY = 86400.0


@dataclass(frozen=True)
# ID: 6550a504-7a08-4aac-8040-84cbab31749f
class ReapCandidate:
    """A stale var/tmp entry selected for reaping."""

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
    skipped (fail-closed). This is selection only — deletion is ``_reap`` — so
    the predicate is a pure, testable function. An absent or non-directory
    ``tmp_root`` yields an empty list, never an error.
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


def _reap(candidate: ReapCandidate, tmp_root: Path, file_service: FileService) -> bool:
    """Delete one stale entry through FileService. Returns True only if it is gone.

    Refuses (reports, never raises) a symlink, a path that does not resolve to a
    direct child of ``tmp_root`` (ADR-117 D3 hard boundary), a path outside the
    service's repository, or a guard refusal. FileHandler's tree removal is
    best-effort, so success is the entry's absence afterwards, not the call's
    return.
    """
    path = candidate.path
    if path.is_symlink():
        logger.warning("var_tmp_janitor: %s is a symlink — refusing", path)
        return False
    if not path.exists():
        logger.warning("var_tmp_janitor: %s is already gone", path)
        return False
    try:
        resolved = path.resolve()
        if resolved.parent != tmp_root.resolve():
            logger.warning(
                "var_tmp_janitor: %s resolves outside var/tmp — refusing", path
            )
            return False
        rel = resolved.relative_to(file_service.repo_path).as_posix()
        if resolved.is_dir():
            file_service.remove_tree(rel)
        else:
            file_service.remove_file(rel)
    except (OSError, ValueError, RuntimeError) as exc:
        logger.warning("var_tmp_janitor: failed to remove %s: %s", path, exc)
        return False
    if path.exists():
        logger.warning("var_tmp_janitor: %s still present after removal", path)
        return False
    return True


# ID: cf53fbdb-6508-40d4-9aa4-2cdfe509b67d
class VarTmpJanitorWorker(Worker):
    """ADR-117 Phase 2 — retention janitor for the var/tmp ephemeral-scratch surface.

    Deletes stale entries older than ``RETENTION_DAYS``, capped at
    ``MAX_REAP_PER_RUN`` per run, and reports what it removed. Classed
    ``governance`` (a deterministic system-state janitor, like
    ``canary_janitor``), not ``sensing`` — it is not an audit-rule sensor.
    """

    declaration_name = "var_tmp_janitor"

    def __init__(self) -> None:
        from shared.infrastructure.bootstrap_registry import BootstrapRegistry

        super().__init__()
        repo_root: Path = BootstrapRegistry.get_repo_path()
        self._tmp_root: Path = repo_root.joinpath(*_TMP_RELPATH)
        self._file_service = FileService(repo_root)

    # ID: 20f804ec-8083-4beb-85f0-145eda4797b9
    async def run(self) -> None:
        """Scan var/tmp and delete stale entries past the retention window."""
        await self.post_heartbeat()

        candidates = find_reap_candidates(self._tmp_root, now_ts=time.time())
        total_entries = _count_entries(self._tmp_root)
        to_reap = candidates[:MAX_REAP_PER_RUN]
        skipped_over_cap = len(candidates) - len(to_reap)

        reaped: list[ReapCandidate] = [
            c for c in to_reap if _reap(c, self._tmp_root, self._file_service)
        ]
        reclaimed_bytes = sum(c.size_bytes for c in reaped)
        oldest_days = max((c.age_days for c in candidates), default=0.0)

        await self.post_report(
            "var_tmp_janitor.reap",
            {
                "mode": "delete",  # ADR-117 D5 Phase 2
                "tmp_root": str(self._tmp_root),
                "total_entries": total_entries,
                "retention_days": RETENTION_DAYS,
                "reap_candidates": len(candidates),
                "reaped": len(reaped),
                "failed": len(to_reap) - len(reaped),
                "skipped_over_cap": max(skipped_over_cap, 0),
                "max_reap_per_run": MAX_REAP_PER_RUN,
                "oldest_candidate_days": round(oldest_days, 1),
                "reclaimed_bytes": reclaimed_bytes,
                "sample": [c.path.name for c in reaped[:10]],
            },
        )
        if reaped:
            logger.info(
                "var_tmp_janitor: reaped %d/%d stale var/tmp entries, %d bytes reclaimed",
                len(reaped),
                len(candidates),
                reclaimed_bytes,
            )
