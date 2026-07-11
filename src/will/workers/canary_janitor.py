# src/will/workers/canary_janitor.py
"""Canary Sandbox Janitor (ADR-147) — retention backstop for work/canary/.

`CrateProcessingService._run_canary_validation` (src/body/services/
crate_processing_service.py) creates a repo snapshot under
`work/canary/sandbox_<crate_id>/` for each canary trial and relies solely on
its own `try/finally` to `shutil.rmtree` it afterward. That is the *only*
cleanup path — there is no age-based backstop. On 2026-07-11 a ~61-hour
systemd watchdog SIGABRT-restart storm (2026-06-26 20:38 -> 2026-06-29 09:24,
fixed by the watchdog pinger in `cli/commands/daemon.py`) repeatedly killed
`core-daemon` mid-canary-trial; a hard SIGABRT bypasses Python's `finally`
entirely, so every in-flight sandbox at kill time was orphaned. 1,948 stale
`sandbox_fix_*` directories accumulated (~14G) before anyone noticed.

This worker is that backstop: it scans `work/canary/` and deletes sandbox
directories older than the retention threshold. Unlike `var_tmp_janitor`
(ADR-117 Phase 1, report-only — `var/tmp/` can hold arbitrary scratch content
from many sources), a `work/canary/sandbox_*` directory is exclusively a
transient repo snapshot produced by this codebase for the duration of a
single canary trial; once stale it has no retention value, so this worker
deletes directly rather than only reporting (ADR-147 D5). Selection is a
pure function (unit-testable without the daemon); only `run()` performs the
deletion. Deletion is direct `shutil.rmtree`, not routed through
`FileHandler` — ADR-147 D4 explains why (`work/` has no
`target_class_boundaries.yaml` entry and would misclassify as the strictest
`repo-source` tier).
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

# Governor-tunable dials, mirroring var_tmp_janitor's pattern.
RETENTION_SECONDS: int = 3600  # 1 hour — far past any normal canary trial duration
MAX_REAP_PER_RUN: int = 50

_SANDBOX_PREFIX = "sandbox_"
_CANARY_RELPATH = ("work", "canary")


@dataclass(frozen=True)
# ID: 529f408f-8a4f-4dd2-8d9e-06a3c0f1e4b1
class StaleSandbox:
    """A stale `work/canary/sandbox_*` directory selected for removal."""

    path: Path
    age_seconds: float
    size_bytes: int


# ID: 64cfff54-8546-4206-8501-3823481a84a3
def find_stale_sandboxes(
    canary_root: Path,
    *,
    now_ts: float,
    retention_seconds: int = RETENTION_SECONDS,
) -> list[StaleSandbox]:
    """Select stale top-level `sandbox_*` entries under `canary_root`.

    An entry is a candidate iff its name starts with `sandbox_` (the fixed
    prefix `_run_canary_validation` uses — anything else under
    `work/canary/` is out of this worker's scope) AND its mtime is older
    than `retention_seconds`. Entries whose mtime cannot be read are
    skipped (fail-closed). This is selection only — no deletion — so the
    predicate is a pure, testable function. An absent or non-directory
    `canary_root` yields an empty list, never an error.
    """
    if not canary_root.is_dir():
        return []
    candidates: list[StaleSandbox] = []
    for entry in sorted(canary_root.iterdir()):
        if not entry.name.startswith(_SANDBOX_PREFIX):
            continue
        try:
            mtime = entry.stat().st_mtime
        except OSError:
            logger.warning(
                "canary_janitor: cannot stat %s — skipping (fail-closed)", entry
            )
            continue
        age_seconds = now_ts - mtime
        if age_seconds <= retention_seconds:
            continue
        candidates.append(
            StaleSandbox(
                path=entry,
                age_seconds=age_seconds,
                size_bytes=_entry_size(entry),
            )
        )
    return candidates


def _entry_size(entry: Path) -> int:
    """Best-effort byte size of a directory tree (advisory, for reporting)."""
    try:
        return sum(p.stat().st_size for p in entry.rglob("*") if p.is_file())
    except OSError:
        return 0


def _reap(candidate: StaleSandbox) -> bool:
    """Best-effort delete of a stale sandbox. Returns True on success."""
    try:
        shutil.rmtree(candidate.path)
        return True
    except OSError as exc:
        logger.warning("canary_janitor: failed to remove %s: %s", candidate.path, exc)
        return False


# ID: 92fe4027-a61e-4263-af7b-3579e166d818
class CanaryJanitorWorker(Worker):
    """Retention backstop for orphaned `work/canary/sandbox_*` directories.

    Deletes sandbox directories older than `RETENTION_SECONDS`, capped at
    `MAX_REAP_PER_RUN` per run. Classed `governance` (a deterministic
    system-state janitor, like `var_tmp_janitor`), not `sensing` — it is not
    an audit-rule sensor.
    """

    declaration_name = "canary_janitor"

    def __init__(self) -> None:
        from shared.infrastructure.bootstrap_registry import BootstrapRegistry

        super().__init__()
        repo_root: Path = BootstrapRegistry.get_repo_path()
        self._canary_root: Path = repo_root.joinpath(*_CANARY_RELPATH)

    # ID: ef2e83d9-409d-4cd3-9efc-91eaebea3490
    async def run(self) -> None:
        """Scan work/canary/ and delete stale sandboxes past the retention window."""
        await self.post_heartbeat()

        candidates = find_stale_sandboxes(self._canary_root, now_ts=time.time())
        to_reap = candidates[:MAX_REAP_PER_RUN]
        skipped_over_cap = len(candidates) - len(to_reap)

        reaped: list[StaleSandbox] = [c for c in to_reap if _reap(c)]
        reclaimed_bytes = sum(c.size_bytes for c in reaped)

        await self.post_report(
            "canary_janitor.reap",
            {
                "mode": "delete",
                "canary_root": str(self._canary_root),
                "reap_candidates": len(candidates),
                "reaped": len(reaped),
                "failed": len(to_reap) - len(reaped),
                "skipped_over_cap": max(skipped_over_cap, 0),
                "max_reap_per_run": MAX_REAP_PER_RUN,
                "retention_seconds": RETENTION_SECONDS,
                "reclaimed_bytes": reclaimed_bytes,
                "sample": [c.path.name for c in reaped[:10]],
            },
        )
        if reaped:
            logger.info(
                "canary_janitor: reaped %d/%d stale sandbox(es), %d bytes reclaimed",
                len(reaped),
                len(candidates),
                reclaimed_bytes,
            )
