# tests/body/sandbox/test_repo_tests.py
"""Repository tests run only through the sandbox (ADR-132 D10.10, M2).

``body.sandbox.repo_tests.run_tests`` replaces the pytest subprocess the
services account used to start itself. What it sends to the sandbox, and how
a result becomes an ActionResult: a job that did not run is never ok.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from body.sandbox import repo_tests
from body.sandbox.models import SandboxResult


BOUND = Path("/opt/core/repo")


def _result(**kw: object) -> SandboxResult:
    base: dict[str, object] = {
        "status": "passed",
        "completeness": "full",
        "isolation": "local",
        "exit_code": 0,
        "stdout": "3 passed in 0.10s\n",
    }
    base.update(kw)
    return SandboxResult(**base)  # type: ignore[arg-type]


async def _run(scratch: Path, result: SandboxResult, **kw: object):
    fake = AsyncMock(return_value=result)
    with (
        patch.object(repo_tests, "run_repo_code", fake),
        patch.object(repo_tests, "_persist_result_to_db", AsyncMock()),
        patch(
            "shared.infrastructure.bootstrap_registry.BootstrapRegistry.get_repo_path",
            return_value=BOUND,
        ),
    ):
        action = await repo_tests.run_tests(repo_root=scratch, **kw)  # type: ignore[arg-type]
    return action, fake.call_args


async def test_targets_and_markers_reach_the_sandbox(scratch: Path) -> None:
    _, call = await _run(
        scratch,
        _result(),
        target="tests/test_a.py",
        extra_targets=["tests/test_b.py"],
        markers="not integration",
    )
    request = call.args[0]
    assert request.targets == ("tests/test_a.py", "tests/test_b.py")
    assert request.markers == "not integration"
    assert request.tree == scratch
    # The copy goes to the bound repository's inbox, the only one the
    # service reads, even when the tree is a flow worktree.
    assert call.kwargs["repo_root"] == BOUND


async def test_without_target_the_whole_tests_tree_runs(scratch: Path) -> None:
    _, call = await _run(scratch, _result(), extra_targets=["ignored.py"])
    assert call.args[0].targets == ("tests",)


async def test_law_beside_the_tree_is_copied_in(scratch: Path) -> None:
    (scratch / ".intent").mkdir()
    _, call = await _run(scratch, _result())
    assert call.args[0].law == (scratch / ".intent",)


async def test_mode_comes_from_core_sandbox_mode(
    scratch: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CORE_SANDBOX_MODE", "service")
    _, call = await _run(scratch, _result())
    assert call.kwargs["mode"] == "service"
    monkeypatch.delenv("CORE_SANDBOX_MODE")
    _, call = await _run(scratch, _result())
    assert call.kwargs["mode"] == "local"


async def test_a_full_pass_is_ok_with_pytests_summary(scratch: Path) -> None:
    action, _ = await _run(scratch, _result())
    assert action.ok
    assert action.data["summary"] == "3 passed in 0.10s"
    assert action.data["isolation"] == "local"


async def test_failure_summary_is_pytests_line(scratch: Path) -> None:
    action, _ = await _run(
        scratch,
        _result(
            status="failed", exit_code=1, stdout="E boom\n1 failed, 2 passed in 0.2s\n"
        ),
    )
    assert not action.ok
    assert action.data["error"] == "1 failed, 2 passed in 0.2s"


@pytest.mark.parametrize(
    ("status", "completeness", "reason"),
    [
        ("not_run", "none", "every selected test was excluded by the sandbox"),
        ("not_run", "none", "sandbox service unavailable: refused"),
        ("error", "none", "the bootstrap produced no report"),
        ("timeout", "none", "the job outlived its timeout"),
        ("passed", "partial", "integration tests excluded"),
    ],
)
async def test_anything_but_a_full_pass_is_not_ok(
    scratch: Path, status: str, completeness: str, reason: str
) -> None:
    # The old runner counted pytest exit 5 under a marker filter as a pass.
    action, _ = await _run(
        scratch,
        _result(status=status, completeness=completeness, reason=reason, stdout=""),
        markers="not integration",
    )
    assert not action.ok
    assert reason in action.data["summary"]


def test_evidence_is_skipped_without_a_file_handler() -> None:
    repo_tests._log_test_result_to_file({"status": "passed"}, None)
    repo_tests._store_failure_artifact({"status": "failed"}, None)


def test_failure_artifact_written_unless_passed(scratch: Path) -> None:
    fh = MagicMock()
    fh.repo_path = scratch
    repo_tests._store_failure_artifact({"status": "not_run"}, fh)
    fh.write_runtime_json.assert_called_once()
    repo_tests._store_failure_artifact({"status": "passed"}, fh)
    fh.remove_file.assert_called_once()


def test_repo_include_drops_runtime_output_secrets_and_caches(scratch: Path) -> None:
    for name in (
        "src",
        "tests",
        "infra",
        "var",
        "reports",
        ".git",
        ".venv",
        ".secrets",
        ".env",
        ".env.test",
        "__pycache__",
        ".coverage.x",
    ):
        (scratch / name).mkdir()
    (scratch / "pyproject.toml").write_text("")
    include = repo_tests.repo_include(scratch)
    assert {"src", "tests", "infra", "pyproject.toml", "var/prompts", "var/mind"} <= set(include)
    for dropped in (
        "var",
        "reports",
        ".git",
        ".venv",
        ".secrets",
        ".env",
        ".env.test",
        "__pycache__",
        ".coverage.x",
    ):
        assert dropped not in include
