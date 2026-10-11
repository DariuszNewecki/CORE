# tests/body/infrastructure/test_repo_sync.py
"""RepoSync (ADR-132 D10 · D2, C2): CORE's clone follows upstream by
fast-forward only, and an interrupted sync is always recovered to exactly
``from`` or exactly ``to`` on tracked paths, leaving runtime files alone.

Real git repositories throughout; the upstream is a local path standing in
for the https URL.
"""

from __future__ import annotations

import fcntl
import subprocess
from pathlib import Path

import pytest

from body.infrastructure.repo_sync import (
    RepoSync,
    SyncRecoveryRefused,
    repo_lock,
)
from body.infrastructure.storage.file_handler import FileHandler
from shared.infrastructure.git_service import GitService
from shared.path_resolver import PathResolver


class _Crash(BaseException):
    """Process death: bypasses every ``except Exception``."""


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo: Path, files: dict[str, str], msg: str) -> str:
    for rel, body in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(body)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def pair(tmp_path: Path) -> tuple[Path, Path]:
    up = tmp_path / "upstream"
    up.mkdir()
    _git(up, "init", "-q", "-b", "develop")
    _commit(up, {"src/a.py": "a = 1\n"}, "base")
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", "--no-hardlinks", "-b", "develop", str(up), "clone")
    return up, clone


def _sync(clone: Path, url: str | None) -> RepoSync:
    handler = FileHandler(str(clone))
    # Sync mechanics, not IntentGuard: the bare repos carry no law.
    handler._guard_paths = lambda *a, **k: None  # type: ignore[method-assign]
    return RepoSync(GitService(clone), handler, url)


def _journal(clone: Path) -> Path:
    return PathResolver.from_repo(clone).run_dir / "repo-sync.json"


def _head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD")


def _crash_at(name: str):
    def hook(step: str) -> None:
        if step == name:
            raise _Crash(step)

    return hook


# ID: 8662ade5-67cd-4a81-8750-89776c784ba8
def test_no_upstream_means_disabled(pair: tuple[Path, Path]) -> None:
    _, clone = pair
    assert _sync(clone, None).sync().state == "disabled"


# ID: a7cd5054-d4a5-40b5-82ba-6b3059367465
def test_up_to_date(pair: tuple[Path, Path]) -> None:
    up, clone = pair
    assert _sync(clone, str(up)).sync().state == "up_to_date"


# ID: ba389420-cc5c-4ad4-894e-2b9e937e326c
def test_fast_forward_moves_files_and_head(pair: tuple[Path, Path]) -> None:
    up, clone = pair
    new = _commit(up, {"src/a.py": "a = 2\n", "src/b.py": "b = 1\n"}, "next")
    outcome = _sync(clone, str(up)).sync()
    assert outcome.state == "fast_forwarded"
    assert _head(clone) == new
    assert (clone / "src/a.py").read_text() == "a = 2\n"
    assert (clone / "src/b.py").exists()
    assert not _journal(clone).exists()
    assert _git(clone, "status", "--porcelain", "--untracked-files=no") == ""


# ID: 986a3ec9-798d-4b04-adf2-6330d3746bc2
def test_clone_ahead_is_left_alone(pair: tuple[Path, Path]) -> None:
    up, clone = pair
    mine = _commit(clone, {"src/c.py": "c = 1\n"}, "core commit")
    assert _sync(clone, str(up)).sync().state == "ahead"
    assert _head(clone) == mine


# ID: 10e9bd16-11fc-4a03-8811-5c0a00bfa85e
def test_divergence_is_refused_not_merged(pair: tuple[Path, Path]) -> None:
    up, clone = pair
    _commit(up, {"src/a.py": "a = 2\n"}, "upstream")
    mine = _commit(clone, {"src/c.py": "c = 1\n"}, "core commit")
    outcome = _sync(clone, str(up)).sync()
    assert outcome.state == "diverged"
    assert _head(clone) == mine
    assert (clone / "src/a.py").read_text() == "a = 1\n"


# ID: 268572f6-381c-42d4-be49-38bcb0811fd3
def test_uncommitted_tracked_change_blocks_sync(pair: tuple[Path, Path]) -> None:
    up, clone = pair
    _commit(up, {"src/a.py": "a = 2\n"}, "upstream")
    (clone / "src/a.py").write_text("a = 99  # crashed proposal output\n")
    outcome = _sync(clone, str(up)).sync()
    assert outcome.state == "failed"
    assert "uncommitted" in (outcome.reason or "")
    assert (clone / "src/a.py").read_text() == "a = 99  # crashed proposal output\n"
    assert not _journal(clone).exists()


# ID: 7df48c92-de0e-4987-9e52-5e236684b5b6
@pytest.mark.parametrize("step", ["journal", "tree"])
def test_crash_before_head_moves_rolls_back_to_from(
    pair: tuple[Path, Path], step: str
) -> None:
    up, clone = pair
    base = _head(clone)
    _commit(up, {"src/a.py": "a = 2\n", "src/b.py": "b = 1\n"}, "next")
    runtime = clone / "var" / "logs" / "keep.log"
    runtime.parent.mkdir(parents=True)
    runtime.write_text("runtime data\n")

    with pytest.raises(_Crash):
        _sync(clone, str(up)).sync(_after_step=_crash_at(step))
    assert _journal(clone).exists()

    recovered = _sync(clone, str(up)).recover()
    assert recovered is not None and recovered["action"] == "rolled_back"
    assert _head(clone) == base
    assert (clone / "src/a.py").read_text() == "a = 1\n"
    assert not (clone / "src/b.py").exists()
    assert runtime.read_text() == "runtime data\n"
    assert not _journal(clone).exists()
    assert _git(clone, "status", "--porcelain", "--untracked-files=no") == ""


# ID: c700167b-628c-4b24-9c1b-4d507e89c88c
def test_crash_after_head_moved_completes(pair: tuple[Path, Path]) -> None:
    up, clone = pair
    new = _commit(up, {"src/a.py": "a = 2\n"}, "next")
    with pytest.raises(_Crash):
        _sync(clone, str(up)).sync(_after_step=_crash_at("ref"))
    recovered = _sync(clone, str(up)).recover()
    assert recovered is not None and recovered["action"] == "completed"
    assert _head(clone) == new
    assert (clone / "src/a.py").read_text() == "a = 2\n"


# ID: 3b45fa01-a10c-4ad4-87a0-f16ab83fbc66
def test_next_sync_recovers_then_fast_forwards(pair: tuple[Path, Path]) -> None:
    up, clone = pair
    new = _commit(up, {"src/a.py": "a = 2\n"}, "next")
    with pytest.raises(_Crash):
        _sync(clone, str(up)).sync(_after_step=_crash_at("tree"))
    outcome = _sync(clone, str(up)).sync()
    assert outcome.state == "fast_forwarded"
    assert outcome.recovered is not None
    assert _head(clone) == new


# ID: 2bcb9a34-f99c-4f2d-b7b4-4c38e054b35b
def test_journal_with_foreign_head_is_refused(pair: tuple[Path, Path]) -> None:
    up, clone = pair
    _commit(up, {"src/a.py": "a = 2\n"}, "next")
    with pytest.raises(_Crash):
        _sync(clone, str(up)).sync(_after_step=_crash_at("journal"))
    _commit(clone, {"src/c.py": "c = 1\n"}, "someone else moved HEAD")
    with pytest.raises(SyncRecoveryRefused):
        _sync(clone, str(up)).recover()


# ID: 92587455-c242-493a-85a0-514c010b96e3
def test_repo_lock_is_exclusive(pair: tuple[Path, Path]) -> None:
    _, clone = pair
    handler = FileHandler(str(clone))
    handler._guard_paths = lambda *a, **k: None  # type: ignore[method-assign]
    lock_file = PathResolver.from_repo(clone).run_dir / "repo-sync.lock"
    with repo_lock(clone, handler):
        with lock_file.open("r") as other:
            with pytest.raises(BlockingIOError):
                fcntl.flock(other.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    with lock_file.open("r") as other:
        fcntl.flock(other.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(other.fileno(), fcntl.LOCK_UN)


# ID: 5e06db0f-1d4f-4ad8-852d-864b6279a995
def test_crash_mid_checkout_removes_only_the_journal_added_files(
    pair: tuple[Path, Path],
) -> None:
    """read-tree writes files before it writes the index: a crash in between
    leaves new files untracked. Recovery removes exactly the journal's added
    paths; other untracked files (runtime data) stay."""
    up, clone = pair
    base = _head(clone)
    _commit(up, {"src/b.py": "b = 1\n"}, "adds b")
    with pytest.raises(_Crash):
        _sync(clone, str(up)).sync(_after_step=_crash_at("journal"))
    (clone / "src" / "b.py").write_text("b = 1\n")  # partially written checkout
    (clone / "src" / "scratch.txt").write_text("not ours to remove\n")

    recovered = _sync(clone, str(up)).recover()
    assert recovered is not None and recovered["removed"] == ["src/b.py"]
    assert _head(clone) == base
    assert not (clone / "src" / "b.py").exists()
    assert (clone / "src" / "scratch.txt").exists()
