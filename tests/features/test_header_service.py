# tests/features/test_header_service.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Import the function we are testing
from features.self_healing.header_service import _run_header_fix_cycle


@pytest.fixture
def mock_builder_and_repo(tmp_path: Path, mocker):
    """
    A fixture that correctly mocks dependencies for the header service.
    - It points the service's REPO_ROOT to the temporary test directory.
    - It mocks the KnowledgeGraphBuilder to prevent it from running.
    """
    # Mocks REPO_ROOT inside the target module to point to our temp directory
    mocker.patch("features.self_healing.header_service.REPO_ROOT", tmp_path)

    # Mocks the KnowledgeGraphBuilder class
    mock_builder_class = mocker.patch(
        "features.self_healing.header_service.KnowledgeGraphBuilder"
    )

    # Creates a mock instance that will be returned when KnowledgeGraphBuilder is instantiated
    mock_builder_instance = MagicMock()
    mock_builder_class.return_value = mock_builder_instance

    # Return the builder so we can make assertions on it
    return mock_builder_instance


def test_run_header_fix_cycle_no_files(mock_builder_and_repo, caplog):
    """
    Test that the function runs without error when there are no files to process.
    """
    # ACT
    _run_header_fix_cycle(dry_run=True, all_py_files=[])

    # ASSERT
    assert "Scanning 0 files" in caplog.text


def test_run_header_fix_cycle_fixes_in_write_mode(
    mock_builder_and_repo, tmp_path: Path
):
    """
    Verify that fixes are correctly written to disk when dry_run is False.
    This is the core behavior test.
    """
    # ARRANGE: Create a file with a broken header inside the temp directory
    broken_file = tmp_path / "src" / "broken.py"
    broken_file.parent.mkdir(parents=True, exist_ok=True)
    broken_file.write_text("def my_func(): pass\n")

    # ACT: Run the header fix cycle in write mode
    _run_header_fix_cycle(dry_run=False, all_py_files=["src/broken.py"])

    # ASSERT: Check the actual content of the file on disk
    content = broken_file.read_text()
    assert "# src/broken.py" in content
    assert '"""Provides functionality for the broken module."""' in content
    assert "from __future__ import annotations" in content
    assert "def my_func(): pass" in content

    # ASSERT: Check that the knowledge graph is rebuilt after a successful write
    mock_builder_and_repo.build.assert_called_once()


def test_run_header_fix_cycle_handles_read_error(mock_builder_and_repo, caplog):
    """
    Ensure errors during file processing (e.g., file deleted during run) are
    caught and logged without crashing the process.
    """
    # ARRANGE: We pass a path that doesn't exist.

    # ACT
    _run_header_fix_cycle(dry_run=True, all_py_files=["src/nonexistent.py"])

    # ASSERT: Verify that a warning was logged.
    assert "Could not process src/nonexistent.py" in caplog.text
