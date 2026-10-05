"""ADR-169 D3 / ADR-030: a daemon process knows whether it runs the code on disk.

Real git repositories: the identity is git blob ids of src/, so the tests
exercise the same git calls the daemon makes.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from shared.infrastructure import code_identity
from shared.infrastructure.code_identity import (
    capture_loaded_code_identity,
    code_drift,
    loaded_code_identity,
    reset_process_identity,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture(autouse=True)
def _fresh_process() -> Iterator[None]:
    reset_process_identity()
    yield
    reset_process_identity()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    (tmp_path / "src").mkdir()
    (tmp_path / "src/app.py").write_text("x = 1\n")
    (tmp_path / "README").write_text("r\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def test_not_a_daemon_is_inactive_and_never_suspends() -> None:
    drift = code_drift()
    assert drift.state == "inactive"
    assert not drift.suspends_autonomy


def test_captured_code_matches_until_src_changes(repo: Path) -> None:
    identity = capture_loaded_code_identity(repo)
    assert identity and len(identity) == 64
    assert loaded_code_identity() == identity
    assert code_drift(use_cache=False).state == "match"

    (repo / "src/app.py").write_text("x = 2\n")  # uncommitted counts (ADR-030)
    drift = code_drift(use_cache=False)
    assert drift.state == "stale"
    assert drift.suspends_autonomy
    assert drift.loaded_identity == identity
    assert drift.disk_identity != identity


def test_new_untracked_module_is_stale(repo: Path) -> None:
    capture_loaded_code_identity(repo)
    (repo / "src/new.py").write_text("y = 1\n")
    assert code_drift(use_cache=False).state == "stale"


def test_change_outside_src_is_not_stale(repo: Path) -> None:
    capture_loaded_code_identity(repo)
    (repo / "README").write_text("changed\n")
    assert code_drift(use_cache=False).state == "match"


def test_reverting_the_change_matches_again(repo: Path) -> None:
    capture_loaded_code_identity(repo)
    (repo / "src/app.py").write_text("x = 2\n")
    assert code_drift(use_cache=False).state == "stale"
    (repo / "src/app.py").write_text("x = 1\n")
    assert code_drift(use_cache=False).state == "match"


def test_failed_capture_is_unknown_and_suspends(tmp_path: Path) -> None:
    """Not a git work tree: the precondition cannot be evaluated -> fail closed."""
    assert capture_loaded_code_identity(tmp_path) is None
    drift = code_drift(use_cache=False)
    assert drift.state == "unknown"
    assert drift.suspends_autonomy
    assert drift.reason


def test_comparison_is_cached_within_the_window(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    capture_loaded_code_identity(repo)
    assert code_drift().state == "match"
    (repo / "src/app.py").write_text("x = 2\n")
    assert code_drift().state == "match"  # cached
    monkeypatch.setattr(code_identity, "_CACHE_TTL_SEC", 0.0)
    assert code_drift().state == "stale"
