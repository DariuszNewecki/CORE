# tests/shared/infrastructure/validation/test_test_runner__failure_summary.py

"""run_tests() failure-summary derivation — real pytest failures write to
stdout, not stderr; the summary must reflect that, not a generic
"Execution failed" (fix for the same-message-for-every-cause defect
found investigating the #787-adjacent worker test-gen backlog).

Source: shared.infrastructure.validation.test_runner.run_tests
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.infrastructure.validation.test_runner import run_tests


def _mock_subprocess(stdout: bytes, stderr: bytes, returncode: int) -> MagicMock:
    process = MagicMock()
    process.communicate = AsyncMock(return_value=(stdout, stderr))
    process.returncode = returncode
    return process


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
        "shared.infrastructure.validation.test_runner.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=_mock_subprocess(stdout, b"", 1)),
    ):
        with patch(
            "shared.infrastructure.validation.test_runner._persist_result_to_db",
            new=AsyncMock(),
        ):
            result = await run_tests(target="tests/test_x.py")

    assert result.ok is False
    assert result.data["summary"] == "=========================== 1 failed in 0.12s ==================="
    assert result.data["summary"] != "Execution failed"
    assert result.data["error"] == result.data["summary"]


async def test_failure_falls_back_to_stderr_when_stdout_empty() -> None:
    """A genuine subprocess-level crash (no stdout at all) still falls back
    to stderr — the fallback path isn't removed, just no longer the default."""
    with patch(
        "shared.infrastructure.validation.test_runner.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=_mock_subprocess(b"", b"pytest: command not found", 127)),
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
        "shared.infrastructure.validation.test_runner.asyncio.create_subprocess_exec",
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
        "shared.infrastructure.validation.test_runner.asyncio.create_subprocess_exec",
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
        "shared.infrastructure.validation.test_runner.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=_mock_subprocess(stdout, b"", 1)),
    ):
        with patch(
            "shared.infrastructure.validation.test_runner._persist_result_to_db",
            new=AsyncMock(),
        ):
            result = await run_tests(target="tests/test_x.py")

    assert result.data["summary"] == "No test summary found."
