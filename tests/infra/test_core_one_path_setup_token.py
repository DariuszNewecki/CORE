"""core-one-path-setup asks for the GitHub token only at a terminal.

core-deploy runs the script after a merge with empty stdin (governor
2026-10-15). There `read` fails under ``set -e`` and the deploy was refused;
the prompt is now skipped. The real ``ask_token`` function is cut from the
script and run in bash with ``say`` and ``write_file`` stubbed.
"""

from __future__ import annotations

import os
import pty
import re
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = (REPO / "infra" / "core-one-path-setup").read_text()
_FN = re.search(r"^ask_token\(\) \{.*?^\}$", SCRIPT, re.S | re.M)
assert _FN, "ask_token not found in infra/core-one-path-setup"
HARNESS = (
    "set -euo pipefail\nDRY=0\n"
    'say() { echo "$*"; }\n'
    'write_file() { cat > "$1"; }\n' + _FN.group(0) + '\nask_token "$1"\necho done\n'
)


def _run(token_file: Path, stdin) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", HARNESS, "harness", str(token_file)],
        stdin=stdin,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_without_a_terminal_the_prompt_is_skipped(tmp_path: Path) -> None:
    token = tmp_path / "token"
    done = _run(token, subprocess.DEVNULL)
    assert done.returncode == 0, done.stderr
    assert "skipped (no terminal)" in done.stdout and "done" in done.stdout
    assert not token.exists()


def test_the_step_is_called_and_the_old_read_is_gone() -> None:
    assert "\nask_token /etc/core/pipeline-github-token\n" in SCRIPT
    assert SCRIPT.count("read -r -s -p") == 1  # only inside ask_token


def test_at_a_terminal_the_token_is_asked_and_written(tmp_path: Path) -> None:
    token = tmp_path / "token"
    master, slave = pty.openpty()
    try:
        os.write(master, b"ghp_example\n")
        done = _run(token, slave)
    finally:
        os.close(slave)
        os.close(master)
    assert done.returncode == 0, done.stderr
    assert token.read_text() == "ghp_example\n"


def test_an_existing_token_is_kept(tmp_path: Path) -> None:
    token = tmp_path / "token"
    token.write_text("kept\n")
    done = _run(token, subprocess.DEVNULL)
    assert "ok: GitHub token present" in done.stdout
    assert token.read_text() == "kept\n"
