"""core-admin shows warnings and errors only, unless LOG_LEVEL says otherwise (#1021).

Found on the 'Prove it' run: every command printed the runtime's INFO logs
(intent validation, git service, rule extraction) around its own output.
Run as a real process, because the default must be set before
``shared.logger`` configures the root logger at import.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


SRC = Path(__file__).resolve().parents[2] / "src"


def _run(tmp_path: Path, **env: str) -> subprocess.CompletedProcess[str]:
    base = {k: v for k, v in os.environ.items() if k != "LOG_LEVEL"}
    return subprocess.run(
        [sys.executable, "-m", "cli.admin_cli", "law", "--help"],
        cwd=tmp_path,
        env={**base, "PYTHONPATH": str(SRC), **env},
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_no_info_logs_by_default(tmp_path: Path) -> None:
    done = _run(tmp_path)
    assert done.returncode == 0, done.stderr
    assert " INFO " not in done.stderr
    assert "Usage" in done.stdout


def test_log_level_still_wins(tmp_path: Path) -> None:
    done = _run(tmp_path, LOG_LEVEL="INFO")
    assert done.returncode == 0, done.stderr
    assert " INFO " in done.stderr


_LOG_RECORD = re.compile(
    r"^<\d>\d{4}-\d\d-\d\dT|\b(DEBUG|INFO|WARNING|ERROR|CRITICAL) [a-z_]+(\.[a-z_]+)+:",
    re.M,
)


def _core_admin(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {k: os.environ[k] for k in ("PATH", "HOME", "LANG") if k in os.environ}
    env.update(
        PYTHONPATH=str(SRC),
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@t",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@t",
    )
    return subprocess.run(
        [sys.executable, "-m", "cli.admin_cli", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_tutorial_path_prints_no_log_records(tmp_path: Path) -> None:
    """#1174 (proof run 4): `code audit --offline` with no rules printed a
    raw `<3>... ERROR mind.governance.stateless_audit: ...` record, then the
    same refusal again as `Governance error:`. Every step of *Start a
    governed project* is run here; none may put a log record on the terminal."""
    assert _core_admin(tmp_path, "project", "new", "demo", "--write").returncode == 0
    repo = tmp_path / "demo"
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

    refused = _core_admin(repo, "code", "audit", "--offline")
    assert refused.returncode != 0
    assert "no project law declared" in refused.stdout
    assert not _LOG_RECORD.search(refused.stderr), refused.stderr

    adopted = _core_admin(
        repo, "project", "adopt-pack", "core/starter-python", "--write"
    )
    assert adopted.returncode == 0, adopted.stderr[-2000:]
    assert not _LOG_RECORD.search(adopted.stderr), adopted.stderr
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "adopt"],
        cwd=repo,
        check=True,
    )

    passed = _core_admin(repo, "code", "audit", "--offline")
    assert passed.returncode == 0, passed.stdout[-2000:]
    assert not _LOG_RECORD.search(passed.stderr), passed.stderr
