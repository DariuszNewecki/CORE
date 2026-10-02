# tests/cli/test_admin_cli__help_skips_bootstrap.py
"""Subcommand --help no longer builds the whole CoreContext.

Click runs the root callback before a subcommand parses its own arguments, so
`core-admin <group> <cmd> --help` used to bootstrap git, the intent repository,
rule extraction and IntentGuard just to print help.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import typer

from cli.admin_cli import _help_requested
from cli.utils import decorators
from cli.utils.decorators import core_command


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["demo", "consequence-chain", "--help"], True),
        (["--help"], True),
        (["project", "new", "x", "--write"], False),
        (["project", "new", "--", "--help"], False),  # after "--" it is a value
        ([], False),
    ],
)
# ID: d4c93742-74bc-4ea0-a72a-3e7ea6962af0
def test_help_requested(argv: list[str], expected: bool) -> None:
    assert _help_requested(argv) is expected


# ID: 1cce2415-8d72-47ee-afb8-73e9941f3278
async def test_core_command_builds_missing_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Safety net: if the context was skipped but the command runs anyway
    (a literal "--help" option value), core_command builds it."""
    built = MagicMock(name="core_context")
    monkeypatch.setattr(decorators, "_build_core_context", lambda: built)
    seen: dict = {}

    @core_command(dangerous=False, requires_context=True)
    async def _cmd(ctx: typer.Context) -> None:
        seen["obj"] = ctx.obj

    ctx = MagicMock(spec=typer.Context)
    ctx.obj = None
    await _cmd(ctx)

    assert seen["obj"] is built


# ID: 5a6ee244-a4a2-45b2-bb90-1ef1bc5807c4
async def test_core_command_keeps_existing_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        decorators, "_build_core_context", MagicMock(side_effect=AssertionError)
    )
    existing = MagicMock(name="existing")
    seen: dict = {}

    @core_command(dangerous=False, requires_context=True)
    async def _cmd(ctx: typer.Context) -> None:
        seen["obj"] = ctx.obj

    ctx = MagicMock(spec=typer.Context)
    ctx.obj = existing
    await _cmd(ctx)

    assert seen["obj"] is existing
