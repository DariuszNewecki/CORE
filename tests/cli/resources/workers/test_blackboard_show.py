# tests/cli/resources/workers/test_blackboard_show.py
"""`core-admin workers show` — the listing must expose what `workers resolve` needs.

`workers resolve <entry_id>` takes a blackboard entry UUID; the listing is the
only read surface for the governor inbox, so it must print the full ID. It
must also print subjects and payloads as data: a finding message containing
``[python]`` was rendered with the bracketed text swallowed as Rich markup.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

from rich.console import Console

import cli.resources.workers.blackboard as blackboard


def _fake_session_with(rows: list[tuple[Any, ...]]) -> Any:
    session = MagicMock()

    async def _execute(*_args: Any, **_kwargs: Any) -> Any:
        result = MagicMock()
        result.fetchall.return_value = rows
        return result

    session.execute = _execute

    @asynccontextmanager
    async def _get_session() -> Any:
        yield session

    return _get_session


async def _render(rows: list[tuple[Any, ...]], *, show_payload: bool) -> str:
    console = Console(record=True, width=400)
    with (
        patch.object(blackboard, "get_session", _fake_session_with(rows)),
        patch.object(blackboard, "console", console),
    ):
        await blackboard.workers_blackboard_cmd.__wrapped__(
            MagicMock(),
            filter=None,
            status="indeterminate",
            entry_type="finding",
            limit=50,
            show_payload=show_payload,
        )
    return console.export_text()


async def test_show_prints_full_entry_id() -> None:
    entry_id = uuid.uuid4()
    rows = [
        (
            entry_id,
            "finding",
            "indeterminate",
            "python::rule::src/x.py",
            uuid.uuid4(),
            datetime(2026, 10, 6, 12, 0, 0),
            {},
        )
    ]

    out = await _render(rows, show_payload=False)

    assert str(entry_id) in out


async def test_show_does_not_swallow_bracketed_text_as_markup() -> None:
    rows = [
        (
            uuid.uuid4(),
            "finding",
            "indeterminate",
            "python::rule::[python]",
            None,
            None,
            {"message": "add artifact_types: [python] to the entry"},
        )
    ]

    out = await _render(rows, show_payload=True)

    assert "python::rule::[python]" in out
    assert "artifact_types: [python]" in out
