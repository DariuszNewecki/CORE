# tests/admin/test_agent_cli.py
from unittest.mock import MagicMock

from typer.testing import CliRunner

from system.admin import app

runner = CliRunner()


def test_agent_scaffold_success(mocker):
    """
    Tests that the `agent scaffold` command successfully invokes the
    scaffolding logic and exits cleanly.
    """
    # Mock the business logic function that the CLI command calls
    mock_scaffold_logic = mocker.patch(
        "system.admin.agent.scaffold_new_application",
        return_value=(True, "Success!"),
    )
    # Mock the service dependencies that the CLI command initializes
    mocker.patch("system.admin.agent.OrchestratorClient")
    mocker.patch("system.admin.agent.FileHandler")

    result = runner.invoke(
        app, ["agent", "scaffold", "test-app", "A simple test app"]
    )

    assert result.exit_code == 0
    assert "Success!" in result.stdout
    mock_scaffold_logic.assert_called_once()
    # Verify it was called with the correct project name and goal
    call_args = mock_scaffold_logic.call_args[1]
    assert call_args["project_name"] == "test-app"
    assert call_args["goal"] == "A simple test app"


def test_agent_scaffold_failure(mocker):
    """
    Tests that the `agent scaffold` command correctly handles a failure
    from the scaffolding logic and exits with an error code.
    """
    mock_scaffold_logic = mocker.patch(
        "system.admin.agent.scaffold_new_application",
        return_value=(False, "Scaffolding failed."),
    )
    mocker.patch("system.admin.agent.OrchestratorClient")
    mocker.patch("system.admin.agent.FileHandler")

    result = runner.invoke(
        app, ["agent", "scaffold", "test-app", "A simple test app"]
    )

    assert result.exit_code == 1
    assert "Scaffolding failed." in result.stdout
    mock_scaffold_logic.assert_called_once()
