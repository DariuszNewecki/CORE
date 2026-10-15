"""An offline audit leaves nothing behind in the audited repository (#1052).

Found setting up process-governance-tool: `core-admin code audit --offline`
left empty var/workflows/pending_writes and var/logs, made eagerly by
FileHandler and ActionLogger at construction.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


SRC = Path(__file__).resolve().parents[4] / "src"


def _core_admin(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # A plain standalone install: nothing from the test session's environment
    # (it points at the test database), no CORE repository.
    env = {k: os.environ[k] for k in ("PATH", "HOME", "LANG") if k in os.environ}
    env["PYTHONPATH"] = str(SRC)
    return subprocess.run(
        [sys.executable, "-m", "cli.admin_cli", *args],
        cwd=repo,
        env=env,
        input="y\n",
        capture_output=True,
        text=True,
        timeout=300,
    )


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def test_offline_audit_creates_no_var_directory(tmp_path: Path) -> None:
    repo = tmp_path / "adopter"
    (repo / "app").mkdir(parents=True)
    (repo / "app" / "a.py").write_text("x = 1\n")
    _git(repo, "init", "-q")
    assert _core_admin(repo, "project", "init", ".", "--write").returncode == 0
    assert (
        _core_admin(
            repo, "project", "adopt-pack", "core/starter-python", "--write"
        ).returncode
        == 0
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "adopt")

    done = _core_admin(repo, "code", "audit", "--offline", "--format", "json")

    assert '"verdict": "PASS"' in done.stdout, done.stderr[-2000:]
    assert not (repo / "var").exists()
