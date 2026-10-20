"""`tests symbols` joins the gap check, open test failures and attempt history
into one status per public symbol (2026-10-20: the three lived apart, so
nobody could see which symbols were tested, failing or stuck)."""

from __future__ import annotations

from pathlib import Path

from cli.logic.test_symbol_ledger import (
    AttemptStats,
    build_symbol_ledger,
    failing_test_names,
)


_CONFIG = {
    "source_root": "src",
    "test_root": "tests",
    "test_file_suffix": "/test_generated.py",
}


def _repo(tmp_path: Path) -> Path:
    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "mod.py").write_text(
        "def ok():\n    pass\n\n"
        "def broken():\n    pass\n\n"
        "def todo():\n    pass\n\n"
        "def stuck():\n    pass\n\n"
        "class Svc:\n    def go(self):\n        pass\n"
    )
    (pkg / "bad.py").write_text("def x(:\n")
    test_dir = tmp_path / "tests" / "pkg" / "mod"
    test_dir.mkdir(parents=True)
    (test_dir / "test_generated.py").write_text(
        "def test_ok():\n    pass\n\n"
        "def test_broken():\n    pass\n\n"
        "def test_Svc():\n    pass\n\n"
        "class TestSvc:\n    def test_go(self):\n        pass\n"
    )
    return tmp_path


def _ledger(tmp_path: Path) -> dict[str, str]:
    repo = _repo(tmp_path)
    test_file = "tests/pkg/mod/test_generated.py"
    failing = failing_test_names(
        [
            f"python::test.runner.failure::{test_file}::{test_file}::test_broken",
            f"python::test.runner.failure::{test_file}::unknown",
        ]
    )
    attempts = {
        ("src/pkg/mod.py", "todo"): AttemptStats(completed=0, failed=1),
        ("src/pkg/mod.py", "stuck"): AttemptStats(completed=2, failed=1),
    }
    rows = build_symbol_ledger(
        repo, ["src/pkg/mod.py", "src/pkg/bad.py"], _CONFIG, attempts, failing, 3
    )
    return {f"{r.source_file}::{r.symbol}": r.status for r in rows}


def test_each_symbol_gets_one_status(tmp_path: Path) -> None:
    assert _ledger(tmp_path) == {
        "src/pkg/bad.py::*": "unreadable",
        "src/pkg/mod.py::ok": "passing",
        "src/pkg/mod.py::broken": "failing",
        "src/pkg/mod.py::todo": "untested",
        "src/pkg/mod.py::stuck": "capped",
        "src/pkg/mod.py::Svc": "passing",
        "src/pkg/mod.py::Svc.go": "passing",
    }


def test_capped_counts_landed_attempts_too(tmp_path: Path) -> None:
    """2 landed + 1 failed reaches a cap of 3 (#1211: every attempt counts)."""
    assert _ledger(tmp_path)["src/pkg/mod.py::stuck"] == "capped"


def test_failing_names_parse_class_and_params() -> None:
    tf = "tests/a/test_generated.py"
    assert failing_test_names(
        [
            f"python::test.runner.failure::{tf}::{tf}::TestSvc::test_go[1]",
            f"python::test.runner.failure::{tf}::{tf}::test_run",
            "python::test.runner.failure::short",
        ]
    ) == {tf: {"Svc.go", "run"}}
