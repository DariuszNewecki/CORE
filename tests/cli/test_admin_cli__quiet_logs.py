"""core-admin shows warnings and errors only, unless LOG_LEVEL says otherwise (#1021).

Found on the 'Prove it' run: every command printed the runtime's INFO logs
(intent validation, git service, rule extraction) around its own output.
Run as a real process, because the default must be set before
``shared.logger`` configures the root logger at import.
"""

from __future__ import annotations

import os
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
