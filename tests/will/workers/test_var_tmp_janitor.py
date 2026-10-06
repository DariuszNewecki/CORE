"""ADR-117 — var/tmp janitor selection predicate and Phase-2 deletion.

These exercise the real derivation (`find_reap_candidates`), not a bypass: each
test seeds a temp tree and ages entries with ``os.utime``, then asserts the
age/pin/boundary predicate selects exactly the stale-and-unpinned entries.
`_reap` (actual deletion) is exercised directly, through a real FileService
bound to a temporary repository root.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from body.services.file_service import FileService
from will.workers.var_tmp_janitor import (
    RETENTION_DAYS,
    ReapCandidate,
    _reap,
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


def test_retention_rails_sourced_from_operational_config() -> None:
    """#774 (ADR-040): the retention rails must trace to
    operational_config.yaml, not a src/ literal — guards against a future
    edit silently re-hardcoding them."""
    from shared.infrastructure.intent.operational_config import (
        load_operational_config,
    )
    from will.workers.var_tmp_janitor import MAX_REAP_PER_RUN, RETENTION_DAYS

    cfg = load_operational_config().workers.var_tmp_janitor
    assert RETENTION_DAYS == cfg.retention_days
    assert MAX_REAP_PER_RUN == cfg.max_reap_per_run


# --- Phase 2: deletion (`_reap`) through a real FileService ------------------


def _tmp_root(repo: Path) -> Path:
    root = repo / "var" / "tmp"
    root.mkdir(parents=True)
    return root


def _candidate(path: Path) -> ReapCandidate:
    return ReapCandidate(path=path, age_days=RETENTION_DAYS + 1.0, size_bytes=1)


def test_reap_removes_directory_through_file_service(tmp_path: Path) -> None:
    root = _tmp_root(tmp_path)
    stale = root / "stale_dir"
    stale.mkdir()
    (stale / "f.txt").write_text("x", encoding="utf-8")

    assert _reap(_candidate(stale), root, FileService(tmp_path)) is True
    assert not stale.exists()
    assert root.is_dir()  # var/tmp itself is never deleted


def test_reap_removes_file_through_file_service(tmp_path: Path) -> None:
    root = _tmp_root(tmp_path)
    stale = root / "stale.log"
    stale.write_text("x", encoding="utf-8")

    assert _reap(_candidate(stale), root, FileService(tmp_path)) is True
    assert not stale.exists()


def test_reap_missing_entry_is_reported_not_raised(tmp_path: Path) -> None:
    root = _tmp_root(tmp_path)

    assert _reap(_candidate(root / "gone"), root, FileService(tmp_path)) is False


def test_reap_refuses_symlink_and_leaves_target(tmp_path: Path) -> None:
    """ADR-117 D3: a symlink in var/tmp is never followed or removed."""
    root = _tmp_root(tmp_path)
    target = tmp_path / "src_like"
    target.mkdir()
    (target / "keep.py").write_text("x", encoding="utf-8")
    link = root / "link_out"
    link.symlink_to(target)

    assert _reap(_candidate(link), root, FileService(tmp_path)) is False
    assert link.is_symlink()
    assert (target / "keep.py").exists()


def test_reap_refuses_path_outside_tmp_root(tmp_path: Path) -> None:
    """ADR-117 D3 hard boundary: only direct children of var/tmp are reaped."""
    root = _tmp_root(tmp_path)
    outside = tmp_path / "var" / "reports"
    outside.mkdir()

    assert _reap(_candidate(outside), root, FileService(tmp_path)) is False
    assert outside.exists()


def test_reap_refuses_path_outside_the_service_repository(tmp_path: Path) -> None:
    """The FileHandler chokepoint bounds deletion to its repository."""
    repo = tmp_path / "repo"
    repo.mkdir()
    foreign_root = _tmp_root(tmp_path / "elsewhere")
    foreign = foreign_root / "stale_dir"
    foreign.mkdir()

    assert _reap(_candidate(foreign), foreign_root, FileService(repo)) is False
    assert foreign.exists()
