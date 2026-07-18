# tests/cli/commands/coverage/test_generation_commands.py

"""#809: generate-adaptive / generate-adaptive-batch require --write.

The legacy adaptive generator (EnhancedTestGenerator, deprecated per
ADR-135 D7) has no dry-run contract and writes test files unconditionally.
Omitting --write must exit locally without ever calling the API — the
route-level 422 (tests/api/v1/test_coverage_routes.py) is defense in depth,
not the only guard.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import typer

from cli.commands.coverage.generation_commands import (
    generate_adaptive_batch_command,
    generate_adaptive_command,
)


def _rendered(mock_print: AsyncMock) -> str:
    return "\n".join(str(call.args[0]) for call in mock_print.call_args_list)


async def test_generate_adaptive_without_write_exits_locally_no_api_call():
    with patch(
        "cli.commands.coverage.generation_commands.CoreApiClient"
    ) as client_cls:
        with pytest.raises(typer.Exit) as exc:
            await generate_adaptive_command.__wrapped__(
                SimpleNamespace(),
                file_path="src/foo/bar.py",
                write=False,
                max_failures=3,
            )
        assert exc.value.exit_code == 2
        client_cls.assert_not_called()


async def test_generate_adaptive_with_write_calls_api():
    with patch(
        "cli.commands.coverage.generation_commands.CoreApiClient"
    ) as client_cls:
        client = client_cls.return_value
        client.coverage_generate = AsyncMock(return_value={"run_id": "abc"})
        client.poll_coverage_run = AsyncMock(
            return_value={"status": "completed", "result": {}}
        )

        await generate_adaptive_command.__wrapped__(
            SimpleNamespace(),
            file_path="src/foo/bar.py",
            write=True,
            max_failures=3,
        )

        client.coverage_generate.assert_awaited_once_with(
            target_file="src/foo/bar.py", write=True
        )


async def test_generate_adaptive_batch_without_write_exits_locally_no_api_call():
    with patch(
        "cli.commands.coverage.generation_commands.CoreApiClient"
    ) as client_cls:
        with pytest.raises(typer.Exit) as exc:
            await generate_adaptive_batch_command.__wrapped__(
                SimpleNamespace(), priority="all", write=False
            )
        assert exc.value.exit_code == 2
        client_cls.assert_not_called()


async def test_generate_adaptive_batch_priority_checked_before_write():
    """Bad priority is reported before the write gate — matches the API
    route's own validation ordering (priority, then write)."""
    with patch(
        "cli.commands.coverage.generation_commands.CoreApiClient"
    ) as client_cls:
        with pytest.raises(typer.Exit) as exc:
            await generate_adaptive_batch_command.__wrapped__(
                SimpleNamespace(), priority="bogus", write=False
            )
        assert exc.value.exit_code == 1
        client_cls.assert_not_called()


async def test_generate_adaptive_batch_with_write_calls_api():
    with patch(
        "cli.commands.coverage.generation_commands.CoreApiClient"
    ) as client_cls:
        client = client_cls.return_value
        client.coverage_generate_batch = AsyncMock(return_value={"run_id": "abc"})
        client.poll_coverage_run = AsyncMock(
            return_value={"status": "completed", "result": {}}
        )

        await generate_adaptive_batch_command.__wrapped__(
            SimpleNamespace(), priority="all", write=True
        )

        client.coverage_generate_batch.assert_awaited_once_with(
            priority="all", write=True
        )


async def test_generate_adaptive_renders_real_result_fields():
    """#813: the rendering used to key off fields (sandbox_passed,
    patterns_learned, ...) that EnhancedSingleFileRemediationService never
    returns. Pin that the real fields (file, test_file, final_coverage)
    now actually reach the console."""
    with (
        patch("cli.commands.coverage.generation_commands.CoreApiClient") as client_cls,
        patch("cli.commands.coverage.generation_commands.console.print") as mock_print,
    ):
        client = client_cls.return_value
        client.coverage_generate = AsyncMock(return_value={"run_id": "abc"})
        client.poll_coverage_run = AsyncMock(
            return_value={
                "status": "completed",
                "result": {
                    "status": "completed",
                    "file": "src/foo/bar.py",
                    "test_file": "tests/foo/test_bar.py",
                    "final_coverage": 92.5,
                },
            }
        )

        await generate_adaptive_command.__wrapped__(
            SimpleNamespace(), file_path="src/foo/bar.py", write=True, max_failures=3
        )

        rendered = _rendered(mock_print)
        assert "tests/foo/test_bar.py" in rendered
        assert "92.5" in rendered
        assert "Completed generation cycle" in rendered


async def test_generate_adaptive_batch_renders_summary_and_failed_files():
    """#813: same defect on the batch side — the rendering keyed off
    files_processed/tests_sandbox_passed/tests_saved, none of which
    BatchRemediationService.process_batch() returns. Pin the real
    processed/summary/results shape now renders, including failures."""
    with (
        patch("cli.commands.coverage.generation_commands.CoreApiClient") as client_cls,
        patch("cli.commands.coverage.generation_commands.console.print") as mock_print,
    ):
        client = client_cls.return_value
        client.coverage_generate_batch = AsyncMock(return_value={"run_id": "abc"})
        client.poll_coverage_run = AsyncMock(
            return_value={
                "status": "completed",
                "result": {
                    "status": "completed",
                    "processed": 3,
                    "summary": {"success": 1, "failed": 2, "skipped": 0},
                    "results": [
                        {"file": "src/a.py", "status": "success"},
                        {"file": "src/b.py", "status": "failed", "error": "boom"},
                        {"file": "src/c.py", "status": "failed", "error": "kaboom"},
                    ],
                },
            }
        )

        await generate_adaptive_batch_command.__wrapped__(
            SimpleNamespace(), priority="all", write=True
        )

        rendered = _rendered(mock_print)
        assert "Success: 1" in rendered
        assert "Failed: 2" in rendered
        assert "src/b.py" in rendered and "boom" in rendered
        assert "src/c.py" in rendered and "kaboom" in rendered
