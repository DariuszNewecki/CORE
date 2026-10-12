# tests/will/test_generation/test_sandbox_runner.py
"""PytestSandboxRunner runs generated tests in the sandbox (ADR-132 D10.10, M2).

The generated test and the workspace's uncommitted files are laid over the
copy of the repository; nothing is written into the tree, and the services'
environment is never handed to the test (the old runner copied os.environ).
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from body.sandbox.models import SandboxResult as JobResult
from will.test_generation import sandbox
from will.test_generation.sandbox import PytestSandboxRunner


REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def scratch() -> Iterator[Path]:
    """A scratch directory under var/tmp (never /tmp)."""
    var_tmp = REPO_ROOT / "var" / "tmp"
    var_tmp.mkdir(parents=True, exist_ok=True)
    d = Path(tempfile.mkdtemp(prefix="gen_sandbox_test_", dir=str(var_tmp)))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _runner(repo_root: Path) -> PytestSandboxRunner:
    return PytestSandboxRunner(file_handler=MagicMock(), repo_root=str(repo_root))


def _job(monkeypatch: pytest.MonkeyPatch, **kw: object) -> AsyncMock:
    base: dict[str, object] = {
        "status": "passed",
        "completeness": "full",
        "isolation": "local",
    }
    base.update(kw)
    fake = AsyncMock(return_value=JobResult(**base))  # type: ignore[arg-type]
    monkeypatch.setattr(sandbox, "run_in_sandbox", fake)
    return fake


async def test_test_and_workspace_files_are_overlaid(
    monkeypatch: pytest.MonkeyPatch, scratch: Path
) -> None:
    fake = _job(
        monkeypatch,
        passed_ids=[
            "test_sym_sandbox.py::test_a",
            "test_sym_sandbox.py::TestB::test_b[1]",
        ],
    )
    workspace = SimpleNamespace(get_crate_content=lambda: {"src/pkg/mod.py": "X = 1\n"})
    result = await _runner(scratch).run(
        "def test_a(): pass", "sym", workspace=workspace
    )  # type: ignore[arg-type]

    assert result.passed and result.error == ""
    assert result.passed_tests == ["test_a", "test_b"]
    assert result.total_tests == 2
    tree, targets = fake.await_args.args
    assert tree == scratch and targets == ["test_sym_sandbox.py"]
    assert fake.await_args.kwargs["overlay"] == [
        ("src/pkg/mod.py", b"X = 1\n"),
        ("test_sym_sandbox.py", b"def test_a(): pass"),
    ]


async def test_failure_reports_output_and_failed_names(
    monkeypatch: pytest.MonkeyPatch, scratch: Path
) -> None:
    _job(
        monkeypatch,
        status="failed",
        failed_ids=["test_sym_sandbox.py::test_a"],
        stdout="1 failed",
        stderr="ImportError: x",
    )
    result = await _runner(scratch).run("code", "sym")
    assert not result.passed
    assert result.error == "1 failed\nImportError: x"
    assert result.failed_tests == ["test_a"]


async def test_not_run_is_not_a_pass(
    monkeypatch: pytest.MonkeyPatch, scratch: Path
) -> None:
    _job(monkeypatch, status="not_run", completeness="none", reason="service down")
    result = await _runner(scratch).run("code", "sym")
    assert not result.passed
    assert "service down" in result.error


async def test_timeout(monkeypatch: pytest.MonkeyPatch, scratch: Path) -> None:
    _job(monkeypatch, status="timeout", completeness="none")
    result = await _runner(scratch).run("code", "sym", timeout_seconds=5)
    assert not result.passed and result.error == "Execution timeout (5s)."


async def test_symbol_name_cannot_escape_the_file_name(
    monkeypatch: pytest.MonkeyPatch, scratch: Path
) -> None:
    fake = _job(monkeypatch)
    await _runner(scratch).run("code", "../evil name")
    assert fake.await_args.args[1] == ["test____evil_name_sandbox.py"]


async def test_end_to_end_generated_test_sees_the_workspace(
    monkeypatch: pytest.MonkeyPatch, scratch: Path
) -> None:
    from body.sandbox import repo_tests

    repo = scratch / "repo"
    (repo / "src" / "pkg").mkdir(parents=True)
    (repo / "src" / "pkg" / "__init__.py").write_text("")
    (repo / "src" / "pkg" / "mod.py").write_text("X = 1\n")
    (repo / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    monkeypatch.setenv("CORE_SANDBOX_MODE", "local")
    monkeypatch.setattr(repo_tests, "_persist_result_to_db", AsyncMock())
    workspace = SimpleNamespace(get_crate_content=lambda: {"src/pkg/mod.py": "X = 2\n"})
    code = "from pkg.mod import X\n\ndef test_future():\n    assert X == 2\n"
    result = await _runner(repo).run(code, "future", workspace=workspace)  # type: ignore[arg-type]
    assert result.passed, result.error
    assert result.passed_tests == ["test_future"]
    assert (repo / "src" / "pkg" / "mod.py").read_text() == "X = 1\n"  # tree untouched
