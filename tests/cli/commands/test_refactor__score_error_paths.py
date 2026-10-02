# tests/cli/commands/test_refactor__score_error_paths.py
"""`refactor score` error paths print through the module console.

They used to call `RefactorDisplay.console`, an instance-only attribute, so
every error path raised AttributeError instead of printing and exiting 1.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer

from cli.commands.refactor import check_file_score


def _client(**overrides) -> MagicMock:
    client = MagicMock()
    client.refactor_threshold = AsyncMock(return_value={"threshold": 60.0})
    client.refactor_score = AsyncMock(**overrides)
    return client


# ID: 8d50709b-240c-4a06-9720-21d2a731b9f2
async def test_score_api_error_exits_1() -> None:
    client = _client(side_effect=RuntimeError("api down"))
    with patch("cli.commands.refactor.CoreApiClient", return_value=client):
        with pytest.raises(typer.Exit) as exc_info:
            await check_file_score(MagicMock(spec=typer.Context), "src/x.py")
    assert exc_info.value.exit_code == 1


# ID: f850d81a-72e9-4395-8cb3-1f2b9be27090
async def test_score_file_not_found_exits_1() -> None:
    client = _client(return_value={"found": False})
    with patch("cli.commands.refactor.CoreApiClient", return_value=client):
        with pytest.raises(typer.Exit) as exc_info:
            await check_file_score(MagicMock(spec=typer.Context), "src/x.py")
    assert exc_info.value.exit_code == 1
