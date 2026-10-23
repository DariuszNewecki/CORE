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


# CORE_TEST_SRC lets the same test be pointed at another checkout's src/
# (e.g. a release tag) to show it fails there.
SRC = Path(
    os.environ.get("CORE_TEST_SRC") or Path(__file__).resolve().parents[4] / "src"
)


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
    assert _core_admin(repo, "project", "init", ".", "--write", "--yes").returncode == 0
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


def test_adopt_pack_in_a_new_project_writes_only_intent(tmp_path: Path) -> None:
    """#1160 (proof run 3, 2.14.5): `project adopt-pack` in a fresh `project
    new` project left empty var/logs and var/workflows; adopting a pack writes
    only under .intent/."""
    assert _core_admin(tmp_path, "project", "new", "demo", "--write").returncode == 0
    repo = tmp_path / "demo"
    assert not (repo / "var").exists()

    adopted = _core_admin(
        repo, "project", "adopt-pack", "core/starter-python", "--write"
    )

    assert adopted.returncode == 0, adopted.stderr[-2000:]
    assert (repo / ".intent").is_dir()
    assert not (repo / "var").exists()
