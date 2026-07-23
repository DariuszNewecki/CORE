# tests/cli/logic/demo/conftest.py
"""Shared fixtures for isolated consequence-chain demo substrate tests (ADR-155)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from shared.infrastructure.git_service import GitService


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def source_repo(tmp_path: Path) -> GitService:
    """Real, throwaway git repo with one commit and no other state — fresh per test."""
    repo_dir = tmp_path / "source"
    repo_dir.mkdir()
    _run(["git", "init"], repo_dir)
    _run(["git", "config", "user.email", "demo@test.local"], repo_dir)
    _run(["git", "config", "user.name", "Demo Test"], repo_dir)
    _run(["git", "config", "commit.gpgsign", "false"], repo_dir)
    (repo_dir / "README.md").write_text("hello\n")
    (repo_dir / ".intent").mkdir()
    (repo_dir / ".intent" / "marker.txt").write_text("intent-marker\n")
    _run(["git", "add", "README.md", ".intent"], repo_dir)
    _run(["git", "commit", "-m", "initial"], repo_dir)
    return GitService(repo_dir)


@pytest.fixture
def demo_state_root(tmp_path: Path) -> Path:
    root = tmp_path / "demo_state"
    root.mkdir()
    return root


@pytest.fixture(scope="session")
def docker_compose_available() -> bool:
    """True only if the `docker compose` v2 subcommand actually works here.

    Gates the Compose-dependent subset of the Phase 1 suite (U07, E04, E07,
    E12 per the Phase1-Map): CI or a dev box without Docker — or with only
    the legacy standalone `docker-compose` v1 binary — still runs the rest
    of the suite (U04-U06, E02, E06) rather than failing outright.
    """
    if not shutil.which("docker"):
        return False
    try:
        result = subprocess.run(
            ["docker", "compose", "version"], capture_output=True, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0
