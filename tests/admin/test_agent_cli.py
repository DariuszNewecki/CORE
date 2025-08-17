# tests/admin/test_agent_cli.py
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from system.admin import app
from system.admin.agent import scaffold_new_application


@pytest.fixture
def mock_scaffolder_deps(mocker, tmp_path):
    """Mocks dependencies for the scaffolding logic."""
    # Mock the Scaffolder class itself to avoid actual file operations
    mock_scaffolder_instance = MagicMock()
    mock_scaffolder_instance.workspace = tmp_path
    mock_scaffolder_instance.project_root = tmp_path / "test-app"
    mocker.patch(
        "system.admin.agent.Scaffolder", return_value=mock_scaffolder_instance
    )

    # Mock the Orchestrator to return a predictable file structure
    mock_orchestrator = MagicMock()
    mock_orchestrator.make_request.return_value = json.dumps(
        {
            "src/main.py": "print('hello')",
            "pyproject.toml": "[tool.poetry]\nname = 'test-app'",
        }
    )

    mock_file_handler = MagicMock()
    mock_file_handler.repo_path = tmp_path

    return mock_scaffolder_instance, mock_orchestrator, mock_file_handler


def test_scaffold_new_application_logic_success(mock_scaffolder_deps):
    """Tests the core logic of scaffolding a new application."""
    mock_scaffolder, mock_orchestrator, mock_file_handler = mock_scaffolder_deps

    success, message = scaffold_new_application(
        project_name="test-app",
        goal="A simple test app",
        orchestrator=mock_orchestrator,
        file_handler=mock_file_handler,
        initialize_git=False,
    )

    assert success is True
    assert "Successfully scaffolded" in message
    # Verify that the scaffolder was called to create the base and write files
    mock_scaffolder.scaffold_base_structure.assert_called_once()
    assert mock_scaffolder.write_file.call_count == 4  # 2 from LLM, 2 for test/CI


def test_scaffold_new_application_handles_llm_failure(mock_scaffolder_deps):
    """Tests that scaffolding fails gracefully if the LLM returns invalid data."""
    mock_scaffolder, mock_orchestrator, mock_file_handler = mock_scaffolder_deps
    mock_orchestrator.make_request.return_value = "this is not json"

    success, message = scaffold_new_application(
        project_name="test-app",
        goal="A simple test app",
        orchestrator=mock_orchestrator,
        file_handler=mock_file_handler,
    )

    assert success is False
    assert "Scaffolding failed" in message
    mock_scaffolder.scaffold_base_structure.assert_not_called()
