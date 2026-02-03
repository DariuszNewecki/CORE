# tests/integration/cli/test_database_resource.py
# ID: tests.integration.cli.test_database_resource
"""
Integration tests for database resource commands.

Tests the new resource-first CLI pattern with actual database operations.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from body.cli.resources.database import app as database_app


runner = CliRunner()


# ID: test_database_sync_help
def test_database_sync_help():
    """Test that database sync command has proper help text."""
    result = runner.invoke(database_app, ["sync", "--help"])

    assert result.exit_code == 0
    assert "Synchronize database schema" in result.stdout
    assert "--write" in result.stdout
    assert "Examples:" in result.stdout


# ID: test_database_migrate_help
def test_database_migrate_help():
    """Test that database migrate command has proper help text."""
    result = runner.invoke(database_app, ["migrate", "--help"])

    assert result.exit_code == 0
    assert "Run pending database migrations" in result.stdout
    assert "--revision" in result.stdout


# ID: test_database_export_help
def test_database_export_help():
    """Test that database export command has proper help text."""
    result = runner.invoke(database_app, ["export", "--help"])

    assert result.exit_code == 0
    assert "Export database contents" in result.stdout
    assert "--format" in result.stdout
    assert "--tables" in result.stdout


# ID: test_database_cleanup_help
def test_database_cleanup_help():
    """Test that database cleanup command has proper help text."""
    result = runner.invoke(database_app, ["cleanup", "--help"])

    assert result.exit_code == 0
    assert "Remove orphaned" in result.stdout
    assert "--target" in result.stdout
    assert "--days" in result.stdout


# ID: test_database_status_help
def test_database_status_help():
    """Test that database status command has proper help text."""
    result = runner.invoke(database_app, ["status", "--help"])

    assert result.exit_code == 0
    assert "health metrics" in result.stdout
    assert "--detailed" in result.stdout


# ID: test_database_no_args_shows_help
def test_database_no_args_shows_help():
    """Test that database with no subcommand shows help."""
    result = runner.invoke(database_app, [])

    # Should show help with available commands
    assert "sync" in result.stdout
    assert "migrate" in result.stdout
    assert "export" in result.stdout
    assert "cleanup" in result.stdout
    assert "status" in result.stdout


@pytest.mark.asyncio
# ID: test_database_sync_dry_run
async def test_database_sync_dry_run(test_session):
    """Test database sync in dry-run mode."""
    # This would need proper async test setup
    # Placeholder for integration test
    pass


@pytest.mark.asyncio
# ID: test_database_status_displays_metrics
async def test_database_status_displays_metrics(test_session):
    """Test that database status shows actual metrics."""
    # This would need proper async test setup
    # Placeholder for integration test
    pass
