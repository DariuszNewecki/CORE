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
