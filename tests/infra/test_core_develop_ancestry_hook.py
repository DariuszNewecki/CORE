"""The `.claude/hooks` ancestry check (ADR-132 D10.12, proposal 0018).

Real git repositories: a development tree and a stand-in for CORE's clone.
The hook must pass anything but `git commit`, stay inert while no clone
exists, refuse a commit whose HEAD lacks core/develop, refuse (fail closed)
when core/develop cannot be fetched, and judge the worktree the commit lands
in rather than the development checkout.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
# The source of the copy installed in .claude/hooks/ (core-law, not in git).
HOOK = REPO / "infra" / "claude-hooks" / "core-develop-ancestry.sh"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo: Path, name: str) -> None:
    (repo / name).write_text(name)
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", name)


@pytest.fixture
def trees(tmp_path: Path) -> tuple[Path, Path]:
    clone = tmp_path / "clone"
    clone.mkdir()
    _git(clone, "init", "-q", "-b", "develop")
    _commit(clone, "base")
    dev = tmp_path / "dev"
    _git(tmp_path, "clone", "-q", "-b", "develop", str(clone), "dev")
    return dev, clone


def _hook(
    dev: Path, clone: Path, command: str, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(dev), "CORE_CLONE": str(clone)}
    payload = json.dumps({"tool_input": {"command": command}, "cwd": str(cwd or dev)})
    return subprocess.run(
        ["bash", str(HOOK)], input=payload, env=env, capture_output=True, text=True
    )


# ID: 188dd5be-d6a6-47ff-83b8-7ac8c8c282aa
def test_non_commit_commands_pass(trees: tuple[Path, Path]) -> None:
    dev, clone = trees
    _commit(clone, "core-work")
    assert _hook(dev, clone, "git status").returncode == 0


# ID: 8421b70e-4e10-4da7-8cb2-ae03e13cfe96
def test_inert_without_a_clone(trees: tuple[Path, Path], tmp_path: Path) -> None:
    dev, _ = trees
    assert _hook(dev, tmp_path / "absent", "git commit -m x").returncode == 0


# ID: cb31d170-e485-450d-8934-420849ab01b7
def test_commit_without_core_develop_is_refused_then_allowed_after_ff(
    trees: tuple[Path, Path],
) -> None:
    dev, clone = trees
    _commit(clone, "core-work")
    refused = _hook(dev, clone, "git add a && git commit -m mine")
    assert refused.returncode == 2
    assert "git merge --ff-only core/develop" in refused.stderr
    _git(dev, "merge", "--ff-only", "core/develop")
    assert _hook(dev, clone, "git commit -m mine").returncode == 0


# ID: 9eb4172c-67db-494a-beb5-99a6d263b1a5
def test_rewritten_core_line_fails_closed(trees: tuple[Path, Path]) -> None:
    dev, clone = trees
    _commit(clone, "core-work")
    _git(dev, "fetch", "-q", str(clone), "develop:refs/heads/core/develop")
    _git(clone, "reset", "-q", "--hard", "HEAD~1")
    _commit(clone, "rewritten")
    refused = _hook(dev, clone, "git commit -m mine")
    assert refused.returncode == 2
    assert "could not fetch core/develop" in refused.stderr


# ID: 7459be6d-4a30-4c8b-91ad-fdb2ebe50c5c
def test_a_worktree_containing_core_develop_may_commit_while_dev_lags(
    trees: tuple[Path, Path], tmp_path: Path
) -> None:
    dev, clone = trees
    _commit(clone, "core-work")
    _git(dev, "fetch", "-q", str(clone), "develop:refs/heads/core/develop")
    wt = tmp_path / "wt"
    _git(dev, "worktree", "add", "-q", "-b", "mine", str(wt), "core/develop")
    assert _hook(dev, clone, "git commit -m mine", cwd=wt).returncode == 0
    assert _hook(dev, clone, f"cd {wt} && git commit -m mine").returncode == 0
    assert _hook(dev, clone, f"git -C {wt} commit -m mine").returncode == 0
    lagging = _hook(dev, clone, "git commit -m mine")
    assert lagging.returncode == 2
    assert str(dev) in lagging.stderr


# ID: 940aca16-7bf1-4ef2-9c35-a0542b228354
def test_a_worktree_lacking_core_develop_is_refused(
    trees: tuple[Path, Path], tmp_path: Path
) -> None:
    dev, clone = trees
    wt = tmp_path / "old"
    _git(dev, "worktree", "add", "-q", "-b", "old", str(wt), "HEAD")
    _commit(clone, "core-work")
    refused = _hook(dev, clone, "git commit -m mine", cwd=wt)
    assert refused.returncode == 2
    assert str(wt) in refused.stderr


# ID: fffd8b47-8b33-4acc-ac97-dff09efb6b18
def test_another_repository_is_judged_by_the_development_checkout(
    trees: tuple[Path, Path], tmp_path: Path
) -> None:
    dev, clone = trees
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-q")
    _commit(clone, "core-work")
    assert _hook(dev, clone, "git commit -m x", cwd=other).returncode == 2
