"""The daemon's PID file is relative to the bound repository, not the cwd.

The release runtime runs the daemon with WorkingDirectory=/opt/core/run,
outside the repository (ADR-132 D10 · D2). A PID path derived from the cwd
came out absolute (/opt/core/run/var/run/...), FileHandler refused it as a
repository-boundary escape, and every daemon process exited at start
(2026-10-12, first release deploy).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cli.commands import daemon
from shared.infrastructure.bootstrap_registry import BootstrapRegistry


@pytest.fixture
def outside_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    run = tmp_path / "run"
    run.mkdir()
    monkeypatch.chdir(run)
    repo = tmp_path / "repo"
    repo.mkdir()
    return repo


def test_default_pid_file_is_repo_relative_when_cwd_is_elsewhere(
    outside_cwd: Path,
) -> None:
    assert daemon._pid_file_for(None, outside_cwd) == Path("var/run/core-daemon.pid")


def test_dedicated_pid_file_is_repo_relative(outside_cwd: Path) -> None:
    assert daemon._pid_file_for("db_sync_worker", outside_cwd) == Path(
        "var/run/core-daemon-worker-db_sync_worker.pid"
    )


def test_without_a_root_it_uses_the_bound_repository(
    outside_cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(BootstrapRegistry, "get_repo_path", lambda: outside_cwd)
    pid = daemon._pid_file_for(None)
    assert not pid.is_absolute()
    assert outside_cwd / pid == outside_cwd / "var" / "run" / "core-daemon.pid"
