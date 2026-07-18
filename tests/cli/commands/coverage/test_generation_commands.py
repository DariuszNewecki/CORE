# tests/cli/commands/coverage/test_generation_commands.py

"""#809: generate-adaptive / generate-adaptive-batch require --write.

Symbol-granular test generation (will.self_healing.symbol_coverage_remediation,
the #814 successor to the retired EnhancedTestGenerator / ADR-135 D7) has no
dry-run contract and writes test files unconditionally. Omitting --write must
exit locally without ever calling the API — the route-level 422
(tests/api/v1/test_coverage_routes.py) is defense in depth, not the only guard.
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


async def test_generate_adaptive_renders_real_result_fields_and_exits_nonzero_on_partial_failure():
    """#814: pin that remediate_file_by_symbol()'s real shape (source_file,
    test_file, summary.{gaps,succeeded,failed}, per-symbol results) reaches
    the console — no final_coverage in the new pipeline (#813 was about the
    predecessor's shape; this is the successor's). A run with any failed
    symbol must NOT be reported as a green success and must exit nonzero —
    "completed" is the orchestration lifecycle status, not per-symbol success."""
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
                    "source_file": "src/foo/bar.py",
                    "test_file": "tests/foo/test_bar.py",
                    "summary": {"gaps": 2, "succeeded": 1, "failed": 1, "skipped": 0},
                    "results": [
                        {"symbol_name": "do_work", "symbol_kind": "function", "ok": True, "error": None},
                        {
                            "symbol_name": "do_other",
                            "symbol_kind": "function",
                            "ok": False,
                            "error": "generation failed for do_other",
                        },
                    ],
                    "files_produced": ["tests/foo/test_bar.py"],
                },
            }
        )

        with pytest.raises(typer.Exit) as exc:
            await generate_adaptive_command.__wrapped__(
                SimpleNamespace(), file_path="src/foo/bar.py", write=True, max_failures=3
            )
        assert exc.value.exit_code == 1

        rendered = _rendered(mock_print)
        assert "tests/foo/test_bar.py" in rendered
        assert "1/2 generated" in rendered
        assert "do_other" in rendered
        assert "generation failed for do_other" in rendered
        assert "1/2 symbol(s) failed" in rendered
        assert "Completed generation cycle" not in rendered


async def test_generate_adaptive_reports_success_and_exits_zero_when_all_symbols_succeed():
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
                    "source_file": "src/foo/bar.py",
                    "test_file": "tests/foo/test_bar.py",
                    "summary": {"gaps": 1, "succeeded": 1, "failed": 0, "skipped": 0},
                    "results": [
                        {"symbol_name": "do_work", "symbol_kind": "function", "ok": True, "error": None},
                    ],
                    "files_produced": ["tests/foo/test_bar.py"],
                },
            }
        )

        await generate_adaptive_command.__wrapped__(
            SimpleNamespace(), file_path="src/foo/bar.py", write=True, max_failures=3
        )

        rendered = _rendered(mock_print)
        assert "Completed generation cycle" in rendered


async def test_generate_adaptive_reports_noop_when_zero_gaps():
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
                    "source_file": "src/foo/bar.py",
                    "test_file": "tests/foo/test_bar.py",
                    "summary": {"gaps": 0, "succeeded": 0, "failed": 0, "skipped": 0},
                    "results": [],
                    "files_produced": [],
                },
            }
        )

        await generate_adaptive_command.__wrapped__(
            SimpleNamespace(), file_path="src/foo/bar.py", write=True, max_failures=3
        )

        rendered = _rendered(mock_print)
        assert "nothing to generate" in rendered


async def test_generate_adaptive_batch_renders_summary_and_failed_files_exits_nonzero():
    """#814: pin remediate_batch_by_symbol()'s real shape — processed/summary
    top-level unchanged from the retired BatchRemediationService, but each
    "results" entry now nests its own per-symbol summary rather than a flat
    status string, so a file can be status="completed" and still count as a
    failure (partial symbol failures). Cover both failure shapes: a hard
    per-file error (status != completed) and a partial-symbol failure. Any
    batch with failures must exit nonzero, not just list them and exit 0."""
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
                        {
                            "file": "src/a.py",
                            "status": "completed",
                            "summary": {"gaps": 1, "succeeded": 1, "failed": 0, "skipped": 0},
                        },
                        {"file": "src/b.py", "status": "error", "error": "boom"},
                        {
                            "file": "src/c.py",
                            "status": "completed",
                            "summary": {"gaps": 2, "succeeded": 0, "failed": 2, "skipped": 0},
                        },
                    ],
                },
            }
        )

        with pytest.raises(typer.Exit) as exc:
            await generate_adaptive_batch_command.__wrapped__(
                SimpleNamespace(), priority="all", write=True
            )
        assert exc.value.exit_code == 1

        rendered = _rendered(mock_print)
        assert "Success: 1" in rendered
        assert "Failed: 2" in rendered
        assert "src/b.py" in rendered and "boom" in rendered
        assert "src/c.py" in rendered and "2 symbol(s) failed" in rendered
        # src/a.py fully succeeded — never printed by file path anywhere.
        assert "src/a.py" not in rendered


async def test_generate_adaptive_batch_exits_zero_when_no_failures():
    with (
        patch("cli.commands.coverage.generation_commands.CoreApiClient") as client_cls,
        patch("cli.commands.coverage.generation_commands.console.print"),
    ):
        client = client_cls.return_value
        client.coverage_generate_batch = AsyncMock(return_value={"run_id": "abc"})
        client.poll_coverage_run = AsyncMock(
            return_value={
                "status": "completed",
                "result": {
                    "status": "completed",
                    "processed": 1,
                    "summary": {"success": 1, "failed": 0, "skipped": 0},
                    "results": [
                        {
                            "file": "src/a.py",
                            "status": "completed",
                            "summary": {"gaps": 1, "succeeded": 1, "failed": 0, "skipped": 0},
                        },
                    ],
                },
            }
        )

        # Must not raise.
        await generate_adaptive_batch_command.__wrapped__(
            SimpleNamespace(), priority="all", write=True
        )
