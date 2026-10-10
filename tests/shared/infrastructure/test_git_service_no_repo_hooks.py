# tests/shared/infrastructure/test_git_service_no_repo_hooks.py
"""CORE's git never runs repository-supplied hooks or fsmonitor (real git).

ADR-132 D10.11 step 1, route R3: `.git/config` and `.git/hooks/` name commands
git runs; whoever can write them could run code as the services account.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from body.atomic.tool_runner import ToolRunner
from shared.infrastructure.git_service import GitService


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _repo_with_planted_hooks(root: Path) -> Path:
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t.invalid")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "a.py").write_text("x = 1\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    marker = root / "hook-ran"
    for hook in ("pre-commit", "post-commit"):
        script = root / ".git" / "hooks" / hook
        script.write_text(f"#!/bin/sh\ntouch {marker}\n")
        script.chmod(0o755)
    monitor = root / "fsmonitor.sh"
    monitor.write_text(f"#!/bin/sh\ntouch {marker}\n")
    monitor.chmod(0o755)
    _git(root, "config", "core.fsmonitor", str(monitor))
    return marker


# ID: f2ff6198-4f41-4364-a52f-e67dc3cc932c
def test_core_commits_without_running_planted_hooks(tmp_path: Path) -> None:
    marker = _repo_with_planted_hooks(tmp_path)
    (tmp_path / "a.py").write_text("x = 2\n")

    GitService(tmp_path).commit_paths(["a.py"], "core commit")

    assert not marker.exists()


# ID: 678b5b7c-ec70-4ea9-bf85-60cdcf5f9a42
def test_tool_runner_git_runs_no_planted_hooks(tmp_path: Path) -> None:
    marker = _repo_with_planted_hooks(tmp_path)

    ToolRunner.run_git(tmp_path, "status", "--porcelain")

    assert not marker.exists()


# ID: 46930a8e-f8c2-4688-852a-50f890d9324d
def test_plain_git_would_have_run_them(tmp_path: Path) -> None:
    """Control: the planted hooks are real — plain git runs them."""
    marker = _repo_with_planted_hooks(tmp_path)
    (tmp_path / "a.py").write_text("x = 3\n")
    _git(tmp_path, "commit", "-q", "-am", "plain")

    assert marker.exists()
