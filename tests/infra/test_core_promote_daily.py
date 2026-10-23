"""core-promote-daily.sh runs only approved code (review findings F2, F3).

The daily promotion runs the live release's own core-admin in a worktree at
the live commit, never main's code, and checks core-claude's gh login by a
real call before it relies on it.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "infra/scripts/core-promote-daily.sh"

FAKE_GH = """#!/bin/bash
case "$1 $2" in
  "auth token") echo bot-token ;;
  "api repos/DariuszNewecki/CORE") echo "${FAKE_PUSH:-true}" ;;
  *) echo "unexpected gh $*" >&2; exit 2 ;;
esac
"""

FAKE_CORE_ADMIN = """#!/bin/bash
{
  echo "args=$*"
  echo "cwd=$(git rev-parse HEAD)"
  echo "token=$CORE_GITHUB_TOKEN"
} > "$RECORD"
"""


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(repo: Path, message: str) -> None:
    ident = ["-c", "user.name=t", "-c", "user.email=t@t"]
    _git(repo, *ident, "commit", "-q", "--allow-empty", "-m", message)


@pytest.fixture
def host(tmp_path: Path) -> dict:
    repo = tmp_path / "dev"
    repo.mkdir()
    _git(repo, "init", "-q")
    _commit(repo, "live")
    live = _git(repo, "rev-parse", "HEAD")
    _commit(repo, "main, not approved")
    _git(repo, "remote", "add", "origin", str(repo))

    release = tmp_path / "releases" / live
    (release / "venv/bin").mkdir(parents=True)
    admin = release / "venv/bin/core-admin"
    admin.write_text(FAKE_CORE_ADMIN)
    admin.chmod(0o755)
    current = tmp_path / "current"
    current.symlink_to(release)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(FAKE_GH)
    (bin_dir / "gh").chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "CORE_DEV_REPO": str(repo),
        "CORE_CURRENT": str(current),
        "RECORD": str(tmp_path / "record"),
    }
    return {"env": env, "live": live, "record": tmp_path / "record", "current": current}


def _run(host: dict, *args: str, **env: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        env={**host["env"], **env},
        capture_output=True,
        text=True,
    )


def test_runs_the_live_releases_core_admin_at_the_live_commit(host: dict) -> None:
    result = _run(host)
    assert result.returncode == 0, result.stderr
    record = host["record"].read_text()
    assert "args=--readonly promote propose\n" in record
    assert f"cwd={host['live']}\n" in record  # not main's newer commit
    assert "token=bot-token\n" in record


def test_an_urgent_promotion_passes_its_flag(host: dict) -> None:
    assert _run(host, "--urgent").returncode == 0
    assert "args=--readonly promote propose --urgent\n" in host["record"].read_text()


def test_a_login_that_cannot_write_stops_before_proposing(host: dict) -> None:
    result = _run(host, FAKE_PUSH="false")
    assert result.returncode == 1
    assert "cannot write" in result.stderr
    assert not host["record"].exists()


def test_a_current_that_is_not_a_release_stops(host: dict, tmp_path: Path) -> None:
    host["current"].unlink()
    host["current"].symlink_to(tmp_path)
    result = _run(host)
    assert result.returncode == 1
    assert not host["record"].exists()


def test_the_script_never_reads_main() -> None:
    assert "origin/main" not in SCRIPT.read_text()
