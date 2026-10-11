"""ADR-169 D3 / ADR-030: a daemon process knows whether it runs the code on disk.

Real git repositories: the identity is git blob ids of src/, so the tests
exercise the same git calls the daemon makes.
"""

from __future__ import annotations

import json
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


# --- ADR-132 D10 · D2 (C4): an installed release is its own identity -------

_SHA = "a" * 40
_WHEEL = "b" * 64


def _release(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> Path:
    meta = tmp_path / "venv" / code_identity.RELEASE_METADATA_NAME
    meta.parent.mkdir(parents=True)
    meta.write_text(body)
    monkeypatch.setattr(code_identity, "release_metadata_path", lambda: meta)
    return meta


# ID: e9b1c90a-0b0c-48ba-9b66-b1b7a1b5b495
def test_release_runtime_identity_is_the_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _release(tmp_path, monkeypatch, json.dumps({"sha": _SHA, "wheel_sha256": _WHEEL}))
    ident = capture_loaded_code_identity(tmp_path / "not-a-repo")
    assert ident == f"release:{_SHA}:{_WHEEL}"
    assert loaded_code_identity() == ident


# ID: cec7fc09-4227-427b-a4a6-d9dc5b12ca6f
def test_release_runtime_never_goes_stale_when_the_clone_changes(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _release(tmp_path, monkeypatch, json.dumps({"sha": _SHA, "wheel_sha256": _WHEEL}))
    capture_loaded_code_identity(repo)
    (repo / "src" / "changed.py").write_text("x = 1\n")
    drift = code_drift(use_cache=False)
    assert drift.state == "release"
    assert drift.suspends_autonomy is False


# ID: bd395150-7317-47e4-a06d-73d9c0526517
@pytest.mark.parametrize(
    "body",
    [
        "not json",
        json.dumps({"sha": _SHA}),
        json.dumps({"sha": "HEAD", "wheel_sha256": _WHEEL}),
        json.dumps(["list"]),
    ],
)
def test_malformed_release_metadata_fails_closed(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str
) -> None:
    _release(tmp_path, monkeypatch, body)
    # A real repo: without the release branch this would capture "match".
    assert capture_loaded_code_identity(repo) is None
    drift = code_drift(use_cache=False)
    assert drift.state == "unknown"
    assert drift.suspends_autonomy is True


# ID: be821874-053c-40ff-b9ac-743dd8d70723
def test_no_release_metadata_keeps_the_src_fingerprint(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        code_identity, "release_metadata_path", lambda: tmp_path / "absent.json"
    )
    ident = capture_loaded_code_identity(repo)
    assert ident is not None and not ident.startswith("release:")
    assert code_drift(use_cache=False).state == "match"


def _layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """/opt/core-like: two releases, `current` -> the first; the process's
    environment is reached through `current`, as the units start it."""
    for sha in (_SHA, "c" * 40):
        venv = tmp_path / "releases" / sha / "venv"
        venv.mkdir(parents=True)
        (venv / code_identity.RELEASE_METADATA_NAME).write_text(
            json.dumps({"sha": sha, "wheel_sha256": _WHEEL})
        )
    (tmp_path / "current").symlink_to(Path("releases") / _SHA)
    meta = tmp_path / "current" / "venv" / code_identity.RELEASE_METADATA_NAME
    monkeypatch.setattr(code_identity, "release_metadata_path", lambda: meta)
    return tmp_path / "current"


# ID: 8fc4fac1-9f7b-4b0e-9614-b9ebc8e0ead1
def test_release_goes_stale_when_current_is_switched_without_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current = _layout(tmp_path, monkeypatch)
    capture_loaded_code_identity(tmp_path / "clone")
    assert code_drift(use_cache=False).state == "release"
    current.unlink()
    current.symlink_to(Path("releases") / ("c" * 40))  # core-deploy switched it
    drift = code_drift(use_cache=False)
    assert drift.state == "stale"
    assert drift.suspends_autonomy is True
    assert drift.disk_identity == f"release:{'c' * 40}:{_WHEEL}"


# ID: 34505102-65a5-4c43-b4a1-0834c519b812
def test_release_unreadable_after_boot_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current = _layout(tmp_path, monkeypatch)
    capture_loaded_code_identity(tmp_path / "clone")
    current.unlink()  # current removed: the deployed release cannot be read
    drift = code_drift(use_cache=False)
    assert drift.state == "unknown"
    assert drift.suspends_autonomy is True
