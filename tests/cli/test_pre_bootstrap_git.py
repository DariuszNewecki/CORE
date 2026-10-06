"""Tests for ``cli.pre_bootstrap_git`` — the one pre-bootstrap git read.

It runs before the environment is bound, so importing it must load no CORE
module at all (checked in a fresh interpreter, since this test process has
already imported plenty).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from cli.pre_bootstrap_git import git_read


_CORE_PACKAGES = ("shared", "body", "mind", "will", "api")


def test_import_loads_no_core_module() -> None:
    src_root = Path(__file__).resolve().parents[2] / "src"
    probe = (
        "import sys; sys.path.insert(0, sys.argv[1]); "
        "import cli.pre_bootstrap_git; "
        f"prefixes = {_CORE_PACKAGES!r}; "
        "print(sorted(m for m in sys.modules if m.split('.')[0] in prefixes))"
    )
    out = subprocess.run(
        [sys.executable, "-I", "-c", probe, str(src_root)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "[]"


def test_reads_head_of_a_repository(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)

    assert git_read(tmp_path, "rev-parse", "--show-toplevel") == str(tmp_path.resolve())


def test_returns_none_outside_a_repository(tmp_path: Path) -> None:
    plain = tmp_path / "not_a_repo"
    plain.mkdir()

    assert git_read(plain, "rev-parse", "HEAD") is None
