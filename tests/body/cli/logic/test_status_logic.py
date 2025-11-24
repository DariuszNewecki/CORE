# tests/body/cli/logic/test_status_logic.py
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.repositories.db.status_service import StatusReport


@pytest.mark.anyio
async def test_get_status_report_delegates_to_db_status() -> None:
    """
    Ensure get_status_report simply delegates to db_status and returns its result.
    """
    import body.cli.logic.status as status_module

    fake_report = StatusReport(
        is_connected=True,
        db_version="PostgreSQL 15.0",
        applied_migrations={"001_init.sql"},
        pending_migrations=[],
    )

    mock_status = AsyncMock(return_value=fake_report)

    # Patch the db_status function used inside the module
    with patch.object(status_module, "db_status", mock_status):
        result = await status_module._get_status_report()

    assert result is fake_report
    mock_status.assert_awaited_once_with()


@pytest.mark.anyio
async def test_status_impl_builds_rich_table() -> None:
    """
    Ensure _status_impl builds and prints a Rich table with the correct structure.
    """
    import body.cli.logic.status as status_module

    fake_report = StatusReport(
        is_connected=True,
        db_version="PostgreSQL 15.0",
        applied_migrations={"001_init.sql"},
        pending_migrations=["002_add_table.sql"],
    )

    mock_status = AsyncMock(return_value=fake_report)

    # Patch db_status and console.print so we don't actually hit the real DB or console
    with (
        patch.object(status_module, "db_status", mock_status),
        patch.object(status_module.console, "print") as mock_print,
    ):
        await status_module._status_impl()

    # We expect a single print call with a Rich Table object
    mock_print.assert_called_once()
    table = mock_print.call_args[0][0]

    # Basic structural checks on the table
    assert table.title == "Database Status"
    headers = [col.header for col in table.columns]
    assert headers == ["Check", "Value"]
