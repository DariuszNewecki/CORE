"""Canary Sandbox Janitor — stale `work/canary/sandbox_*` selection predicate.

These exercise the real derivation (`find_stale_sandboxes`), not a bypass: each
test seeds a temp tree and ages entries with ``os.utime``, then asserts the
age/prefix/boundary predicate selects exactly the stale `sandbox_*` entries.
`_reap` (actual deletion) is exercised separately and directly, since it is a
thin, already-battle-tested `shutil.rmtree` wrapper.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from will.workers.canary_janitor import (
    RETENTION_SECONDS,
    StaleSandbox,
    _reap,
    find_stale_sandboxes,
)


def _age(path: Path, seconds: float) -> None:
    """Backdate a path's mtime by ``seconds`` (set after contents are written)."""
    when = time.time() - seconds
    os.utime(path, (when, when))


def test_selects_only_stale_sandbox_entries(tmp_path: Path) -> None:
    old = tmp_path / "sandbox_fix_deadbeef"
    old.mkdir()
    (old / "f.txt").write_text("x", encoding="utf-8")
    recent = tmp_path / "sandbox_fix_cafef00d"
    recent.mkdir()
    _age(old, RETENTION_SECONDS + 300)

    candidates = find_stale_sandboxes(tmp_path, now_ts=time.time())

    assert {c.path.name for c in candidates} == {"sandbox_fix_deadbeef"}
    assert candidates[0].age_seconds > RETENTION_SECONDS


def test_non_sandbox_entries_are_never_candidates(tmp_path: Path) -> None:
    other = tmp_path / "not_a_sandbox"
    other.mkdir()
    _age(other, RETENTION_SECONDS + 300)

    assert find_stale_sandboxes(tmp_path, now_ts=time.time()) == []


def test_recent_sandboxes_are_kept(tmp_path: Path) -> None:
    fresh = tmp_path / "sandbox_fix_11111111"
    fresh.mkdir()  # mtime ~ now

    assert find_stale_sandboxes(tmp_path, now_ts=time.time()) == []


def test_retention_threshold_is_honored(tmp_path: Path) -> None:
    entry = tmp_path / "sandbox_fix_22222222"
    entry.mkdir()
    _age(entry, RETENTION_SECONDS + 60)

    # Just inside a wider window -> kept; past the default window -> selected.
    assert find_stale_sandboxes(tmp_path, now_ts=time.time(), retention_seconds=7200) == []
    assert len(find_stale_sandboxes(tmp_path, now_ts=time.time())) == 1


def test_absent_root_is_empty_not_error(tmp_path: Path) -> None:
    assert find_stale_sandboxes(tmp_path / "does_not_exist", now_ts=time.time()) == []


def test_reap_removes_directory(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox_fix_33333333"
    sandbox.mkdir()
    (sandbox / "f.txt").write_text("x", encoding="utf-8")
    candidate = StaleSandbox(path=sandbox, age_seconds=9999.0, size_bytes=1)

    assert _reap(candidate) is True
    assert not sandbox.exists()


def test_reap_missing_directory_is_reported_not_raised(tmp_path: Path) -> None:
    missing = tmp_path / "sandbox_fix_44444444"
    candidate = StaleSandbox(path=missing, age_seconds=9999.0, size_bytes=0)

    assert _reap(candidate) is False


def test_retention_rails_sourced_from_operational_config() -> None:
    """#774 (ADR-040): the retention rails must trace to
    operational_config.yaml, not a src/ literal."""
    from shared.infrastructure.intent.operational_config import (
        load_operational_config,
    )
    from will.workers.canary_janitor import MAX_REAP_PER_RUN, RETENTION_SECONDS

    cfg = load_operational_config().workers.canary_janitor
    assert RETENTION_SECONDS == cfg.retention_seconds
    assert MAX_REAP_PER_RUN == cfg.max_reap_per_run
