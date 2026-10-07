# tests/shared/infrastructure/validation/test_test_runner__failure_summary.py

"""run_tests() failure-summary derivation — real pytest failures write to
stdout, not stderr; the summary must reflect that, not a generic
"Execution failed" (fix for the same-message-for-every-cause defect
found investigating the #787-adjacent worker test-gen backlog).

Source: shared.infrastructure.validation.test_runner.run_tests
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.infrastructure.validation.test_runner import run_tests
from shared.utils.subprocess_utils import SubprocessResult


def _mock_subprocess(stdout: bytes, stderr: bytes, returncode: int) -> SubprocessResult:
    # Mirrors run_command_async: decoded with errors="replace", stripped.
    return SubprocessResult(
        stdout=stdout.decode(errors="replace").strip(),
        stderr=stderr.decode(errors="replace").strip(),
        returncode=returncode,
    )


async def test_failure_summary_derived_from_stdout_not_generic_message() -> None:
    """A normal pytest failure (stderr empty, failure text in stdout) must
    surface a real summary line, not the "Execution failed" fallback."""
    stdout = (
        b"============================= test session starts ====\n"
        b"collected 1 item\n\n"
        b"tests/test_x.py::test_foo FAILED\n\n"
        b"=================================== FAILURES ===================\n"
        b"E   AssertionError: assert 2 == 1\n"
        b"=========================== 1 failed in 0.12s ===================\n"
    )
    with patch(
        "shared.infrastructure.validation.test_runner.run_command_async",
        new=AsyncMock(return_value=_mock_subprocess(stdout, b"", 1)),
    ):
        with patch(
            "shared.infrastructure.validation.test_runner._persist_result_to_db",
            new=AsyncMock(),
        ):
            result = await run_tests(target="tests/test_x.py")

    assert result.ok is False
    assert (
        result.data["summary"]
        == "=========================== 1 failed in 0.12s ==================="
    )
    assert result.data["summary"] != "Execution failed"
    assert result.data["error"] == result.data["summary"]


async def test_failure_falls_back_to_stderr_when_stdout_empty() -> None:
    """A genuine subprocess-level crash (no stdout at all) still falls back
    to stderr — the fallback path isn't removed, just no longer the default."""
    with patch(
        "shared.infrastructure.validation.test_runner.run_command_async",
        new=AsyncMock(
            return_value=_mock_subprocess(b"", b"pytest: command not found", 127)
        ),
    ):
        with patch(
            "shared.infrastructure.validation.test_runner._persist_result_to_db",
            new=AsyncMock(),
        ):
            result = await run_tests(target="tests/test_x.py")

    assert result.ok is False
    assert result.data["summary"] == "pytest: command not found"


async def test_success_summary_unchanged() -> None:
    """Passing runs still derive their summary from stdout, as before."""
    stdout = b"collected 3 items\n\n...\n\n===== 3 passed in 0.45s =====\n"
    with patch(
        "shared.infrastructure.validation.test_runner.run_command_async",
        new=AsyncMock(return_value=_mock_subprocess(stdout, b"", 0)),
    ):
        with patch(
            "shared.infrastructure.validation.test_runner._persist_result_to_db",
            new=AsyncMock(),
        ):
            result = await run_tests(target="tests/test_x.py")

    assert result.ok is True
    assert result.data["summary"] == "===== 3 passed in 0.45s ====="
    assert result.data["error"] is None


async def test_no_captured_output_at_all_uses_generic_fallback() -> None:
    """Both streams empty (still a failure) keeps the generic message —
    there's genuinely nothing to summarize."""
    with patch(
        "shared.infrastructure.validation.test_runner.run_command_async",
        new=AsyncMock(return_value=_mock_subprocess(b"", b"", 2)),
    ):
        with patch(
            "shared.infrastructure.validation.test_runner._persist_result_to_db",
            new=AsyncMock(),
        ):
            result = await run_tests(target="tests/test_x.py")

    assert result.ok is False
    assert result.data["summary"] == "Execution failed"


@pytest.mark.parametrize("bad_line", ["No output but has content, no keywords here"])
async def test_summarize_no_keyword_match_reports_honestly(bad_line: str) -> None:
    """stdout present but contains none of the recognized summary keywords
    (passed/failed/error/skipped) — _summarize's own honest 'not found'
    message surfaces rather than silently defaulting to a misleading one."""
    stdout = bad_line.encode()
    with patch(
        "shared.infrastructure.validation.test_runner.run_command_async",
        new=AsyncMock(return_value=_mock_subprocess(stdout, b"", 1)),
    ):
        with patch(
            "shared.infrastructure.validation.test_runner._persist_result_to_db",
            new=AsyncMock(),
        ):
            result = await run_tests(target="tests/test_x.py")

    assert result.data["summary"] == "No test summary found."


async def test_pytest_invoked_with_no_cov() -> None:
    """The runner emits pass/fail evidence, not coverage. Without --no-cov,
    pyproject's addopts --cov applies to every daemon-side run: .coverage is
    rewritten in the repo root each cycle and a timed-out run leaves stray
    .coverage.<host>.<pid>.* shards as untracked files."""
    exec_mock = AsyncMock(return_value=_mock_subprocess(b"1 passed\n", b"", 0))
    with patch(
        "shared.infrastructure.validation.test_runner.run_command_async",
        new=exec_mock,
    ):
        with patch(
            "shared.infrastructure.validation.test_runner._persist_result_to_db",
            new=AsyncMock(),
        ):
            await run_tests(target="tests/test_x.py")

    argv = exec_mock.await_args.args[0]
    assert argv[0] == "pytest"
    assert "--no-cov" in argv


# ID: bf5ad7fd-3eb0-4729-b88a-229fc6e84c6f
async def test_timeout_reports_timed_out_with_exit_code_minus_one(
    tmp_path: Path,
) -> None:
    """A run outliving TEST_RUNNER_TIMEOUT is cut off by asyncio.wait_for
    (run_command_async kills the child on cancellation) and reported as a
    timeout, exit code -1 — the pre-routing contract."""

    async def _hang(*_args: object, **_kwargs: object) -> SubprocessResult:
        await asyncio.sleep(30)
        raise AssertionError("unreachable")

    fake_settings = MagicMock()
    fake_settings.model_extra = {"TEST_RUNNER_TIMEOUT": 0.05}
    fake_settings.REPO_PATH = tmp_path
    with (
        patch("shared.infrastructure.validation.test_runner.settings", fake_settings),
        patch(
            "shared.infrastructure.validation.test_runner.run_command_async",
            new=_hang,
        ),
        patch(
            "shared.infrastructure.validation.test_runner._persist_result_to_db",
            new=AsyncMock(),
        ),
    ):
        result = await run_tests(target="tests/test_x.py")

    assert result.ok is False
    assert result.data["exit_code"] == -1
    assert result.data["stderr"] == "Test run timed out after 0.05s."
    assert result.data["stdout"] == ""
