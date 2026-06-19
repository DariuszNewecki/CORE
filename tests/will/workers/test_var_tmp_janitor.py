"""ADR-117 — var/tmp janitor (Phase 1, report-only) selection predicate.

These exercise the real derivation (`find_reap_candidates`), not a bypass: each
test seeds a temp tree and ages entries with ``os.utime``, then asserts the
age/pin/boundary predicate selects exactly the stale-and-unpinned entries.
Phase 1 has no deletion path, so there is nothing destructive to test here.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from will.workers.var_tmp_janitor import (
    RETENTION_DAYS,
    find_reap_candidates,
)


def _age(path: Path, days: float) -> None:
    """Backdate a path's mtime by ``days`` (set after contents are written)."""
    when = time.time() - days * 86400.0
    os.utime(path, (when, when))


def test_selects_only_stale_unpinned_entries(tmp_path: Path) -> None:
    old = tmp_path / "old_dir"
    old.mkdir()
    (old / "f.txt").write_text("x", encoding="utf-8")
    recent = tmp_path / "recent_dir"
    recent.mkdir()
    _age(old, RETENTION_DAYS + 3)  # comfortably past the cutoff

    candidates = find_reap_candidates(tmp_path, now_ts=time.time())

    assert {c.path.name for c in candidates} == {"old_dir"}
    assert candidates[0].age_days > RETENTION_DAYS


def test_keep_marker_exempts_directory(tmp_path: Path) -> None:
    pinned = tmp_path / "pinned_dir"
    pinned.mkdir()
    (pinned / ".keep").write_text("", encoding="utf-8")
    _age(pinned, 30)

    assert find_reap_candidates(tmp_path, now_ts=time.time()) == []


def test_top_level_keep_file_is_never_a_candidate(tmp_path: Path) -> None:
    keep = tmp_path / ".keep"
    keep.write_text("", encoding="utf-8")
    _age(keep, 30)

    assert find_reap_candidates(tmp_path, now_ts=time.time()) == []


def test_recent_entries_are_kept(tmp_path: Path) -> None:
    fresh = tmp_path / "fresh_dir"
    fresh.mkdir()  # mtime ~ now

    assert find_reap_candidates(tmp_path, now_ts=time.time()) == []


def test_retention_threshold_is_honored(tmp_path: Path) -> None:
    entry = tmp_path / "borderline"
    entry.mkdir()
    _age(entry, RETENTION_DAYS + 1)

    # Just inside a wider window → kept; past the default window → selected.
    assert find_reap_candidates(tmp_path, now_ts=time.time(), retention_days=30) == []
    assert len(find_reap_candidates(tmp_path, now_ts=time.time())) == 1


def test_absent_root_is_empty_not_error(tmp_path: Path) -> None:
    assert find_reap_candidates(tmp_path / "does_not_exist", now_ts=time.time()) == []
