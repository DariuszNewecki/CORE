# tests/body/cli/test_admin_cli.py
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from body.cli.admin_cli import app
from services.repositories.db.status_service import StatusReport

runner = CliRunner()


def test_admin_cli_no_command_launches_interactive_menu():
    with patch("body.cli.admin_cli.launch_interactive_menu") as mock_launch:
        result = runner.invoke(app)
        assert result.exit_code == 0
        mock_launch.assert_called_once()


def test_admin_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "CORE: The Self-Improving System Architect's Toolkit." in result.output


class TestStatusCommand:
    def test_status_command_success(self):
        mock_report = StatusReport(
            is_connected=True,
            db_version="PostgreSQL 15.0",
            applied_migrations={"001_consolidated_schema.sql"},
            pending_migrations=[],
        )

        mock_get_status = AsyncMock(return_value=mock_report)
        with patch("body.cli.logic.status._get_status_report", mock_get_status):
            result = runner.invoke(app, ["inspect", "status"])
            assert result.exit_code == 0
            assert "Database connection: OK" in result.output
            assert "PostgreSQL 15.0" in result.output
            assert "Migrations are up to date" in result.output

    def test_status_command_with_pending_migrations(self):
        mock_report = StatusReport(
            is_connected=True,
            db_version="PostgreSQL 15.0",
            applied_migrations={"001_consolidated_schema.sql"},
            pending_migrations=["002_add_new_table.sql"],
        )

        mock_get_status = AsyncMock(return_value=mock_report)
        with patch("body.cli.logic.status._get_status_report", mock_get_status):
            result = runner.invoke(app, ["inspect", "status"])
            assert result.exit_code == 0
            assert "Found 1 pending migrations" in result.output
            assert "002_add_new_table.sql" in result.output

    def test_status_command_db_connection_failed(self):
        mock_report = StatusReport(
            is_connected=False,
            db_version=None,
            applied_migrations=set(),
            pending_migrations=[],
        )

        mock_get_status = AsyncMock(return_value=mock_report)
        with patch("body.cli.logic.status._get_status_report", mock_get_status):
            result = runner.invoke(app, ["inspect", "status"])
            assert result.exit_code == 0
            assert "Database connection: FAILED" in result.output
