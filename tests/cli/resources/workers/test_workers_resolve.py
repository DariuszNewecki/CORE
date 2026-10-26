# tests/cli/resources/workers/test_workers_resolve.py
"""`core-admin workers resolve` is a governor act through the API (ADR-132 D10.4).

The command sends only the entry id and the reason; who resolved it and under
which authority come back from the server, which reads them from the verified
caller. It has no --by or --authority any more.
"""

from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer
from rich.console import Console

import cli.resources.workers.blackboard as blackboard


_cmd = blackboard.workers_blackboard_resolve_cmd


def test_no_actor_or_authority_options() -> None:
    params = inspect.signature(_cmd.__wrapped__).parameters
    assert "by" not in params
    assert "authority" not in params


async def _run(client: Any) -> str:
    console = Console(record=True, width=300)
    with (
        patch("api.cli.client.CoreApiClient", return_value=client),
        patch.object(blackboard, "console", console),
    ):
        await _cmd.__wrapped__(MagicMock(), entry_id="e-1", reason="stale")
    return console.export_text()


async def test_sends_only_id_and_reason_and_prints_the_servers_stamp() -> None:
    client = MagicMock()
    client.findings.resolve = AsyncMock(
        return_value={
            "resolved_by": "darek",
            "resolution_authority": "principal.governor",
        }
    )
    out = await _run(client)
    client.findings.resolve.assert_awaited_once_with("e-1", "stale")
    assert "RESOLVED by darek under principal.governor" in out


async def test_a_refusal_exits_non_zero() -> None:
    client = MagicMock()
    client.findings.resolve = AsyncMock(
        side_effect=RuntimeError("API error 403: Not the governor")
    )
    with pytest.raises(typer.Exit) as exc:
        await _run(client)
    assert exc.value.exit_code == 1


def test_runs_without_brain_services() -> None:
    """The governor account (core-darek) has no QDRANT_URL; resolve only
    talks to the API, so the decorator must not warm Qdrant (2026-10-26:
    every resolve failed with "QDRANT_URL is not configured")."""
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = MagicMock(qdrant_service=None)
    ctx.obj.registry.get_qdrant_service = AsyncMock(
        side_effect=ValueError("QDRANT_URL is not configured")
    )
    client = MagicMock()
    client.findings.resolve = AsyncMock(
        return_value={"resolved_by": "core-darek", "resolution_authority": "x"}
    )
    with (
        patch("api.cli.client.CoreApiClient", return_value=client),
        patch.object(blackboard, "console", Console(record=True)),
    ):
        _cmd(ctx, entry_id="e-1", reason="stale")
    client.findings.resolve.assert_awaited_once_with("e-1", "stale")
    ctx.obj.registry.get_qdrant_service.assert_not_called()
