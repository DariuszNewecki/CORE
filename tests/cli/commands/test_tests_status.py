# tests/cli/commands/test_tests_status.py
"""Unit tests for the `core-admin tests status` command.

Tests cover:
  - _liveness_color thresholds
  - status command invocable via tests_app without DB errors (DB mocked)
  - tests_app is registered in admin_cli's register_all_commands
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cli.commands.tests import _liveness_color, tests_app


# ── _liveness_color ──────────────────────────────────────────────────────────


# ID: cb58196c-fb7b-42bd-a828-7c701c7da090
def test_liveness_color_none_returns_red() -> None:
    assert _liveness_color(None) == "red"


# ID: a152575e-9190-4464-b3a4-b537609e3e5a
def test_liveness_color_fresh_returns_green() -> None:
    assert _liveness_color(5.0) == "green"
    assert _liveness_color(0.0) == "green"


# ID: fe60b9c2-abd4-47e5-8253-072ed6482a59
def test_liveness_color_stale_returns_yellow() -> None:
    assert _liveness_color(10.0) == "yellow"
    assert _liveness_color(59.0) == "yellow"


# ID: 3ed0de7d-02cd-4316-8d5c-985dbb3f95f6
def test_liveness_color_dead_returns_red() -> None:
    assert _liveness_color(60.0) == "red"
    assert _liveness_color(999.0) == "red"


# ── tests_app registration ───────────────────────────────────────────────────


# ID: 11ad4f92-ce37-4dce-8c75-bb60ea1e77c7
def test_tests_app_registered_in_admin_cli() -> None:
    """tests_app must appear under the 'tests' name in admin_cli's Typer tree."""
    from cli.admin_cli import app

    registered_names = {group.name for group in app.registered_groups}
    assert "tests" in registered_names, (
        "'tests' sub-app not registered in admin_cli.register_all_commands(); "
        "check the add_typer call"
    )


# ── status command wiring (DB mocked) ────────────────────────────────────────


# ID: 9f2b1c4a-d7e8-4f5b-8e3a-0c6d7e1f2a3b
@pytest.mark.asyncio
async def test_tests_status_runs_without_db_errors() -> None:
    """status command should complete without raising when DB returns empty sets."""
    from typer.testing import CliRunner

    runner = CliRunner()

    _empty_result = MagicMock()
    _empty_result.fetchall.return_value = []

    _mock_session = AsyncMock()
    _mock_session.execute = AsyncMock(return_value=_empty_result)
    _mock_session.__aenter__ = AsyncMock(return_value=_mock_session)
    _mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("cli.commands.tests.get_session", return_value=_mock_session):
        result = runner.invoke(tests_app, [])

    # Rich output should contain at least the Worker Liveness panel header
    assert result.exit_code == 0, f"Unexpected exit code {result.exit_code}: {result.output}"
    assert "Worker" in result.output or "Liveness" in result.output
