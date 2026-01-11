"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/action_logger.py
- Symbol: ActionLogger
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:03:44
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from shared.action_logger import ActionLogger


# Detected return type: ActionLogger.log_event returns None (void function)


class TestActionLogger:
    def test_init_with_valid_path_creates_directory(self):
        """Test that ActionLogger creates parent directory when initialized with valid path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_log_path = Path(tmpdir) / "subdir" / "actions.log"

            with patch("shared.action_logger.settings") as mock_settings:
                mock_settings.CORE_ACTION_LOG_PATH = str(test_log_path)
                mock_settings.REPO_PATH = Path(tmpdir)

                logger = ActionLogger()

                assert logger.log_path == test_log_path
                assert test_log_path.parent.exists()

    def test_init_with_empty_path_sets_log_path_to_none(self):
        """Test that ActionLogger sets log_path to None when CORE_ACTION_LOG_PATH is empty."""
        with patch("shared.action_logger.settings") as mock_settings:
            mock_settings.CORE_ACTION_LOG_PATH = ""
            mock_settings.REPO_PATH = Path("/some/repo")

            logger = ActionLogger()

            assert logger.log_path is None

    def test_init_with_missing_path_sets_log_path_to_none(self):
        """Test that ActionLogger sets log_path to None when CORE_ACTION_LOG_PATH is not set."""
        with patch("shared.action_logger.settings") as mock_settings:
            mock_settings.CORE_ACTION_LOG_PATH = None
            mock_settings.REPO_PATH = Path("/some/repo")

            logger = ActionLogger()

            assert logger.log_path is None

    def test_log_event_writes_correct_json_format(self):
        """Test that log_event writes properly formatted JSON with timestamp, event_type, and details."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_log_path = Path(tmpdir) / "actions.log"

            with patch("shared.action_logger.settings") as mock_settings:
                mock_settings.CORE_ACTION_LOG_PATH = str(test_log_path)
                mock_settings.REPO_PATH = Path(tmpdir)

                logger = ActionLogger()

                test_event_type = "test.event.type"
                test_details = {"key1": "value1", "key2": 123}

                logger.log_event(test_event_type, test_details)

                assert test_log_path.exists()

                with open(test_log_path, encoding="utf-8") as f:
                    content = f.read().strip()
                    log_entry = json.loads(content)

                    assert "timestamp_utc" in log_entry
                    assert log_entry["event_type"] == test_event_type
                    assert log_entry["details"] == test_details

                    # Verify timestamp is valid ISO format
                    datetime.fromisoformat(
                        log_entry["timestamp_utc"].replace("Z", "+00:00")
                    )

    def test_log_event_with_none_log_path_does_nothing(self):
        """Test that log_event does nothing when log_path is None."""
        with patch("shared.action_logger.settings") as mock_settings:
            mock_settings.CORE_ACTION_LOG_PATH = None
            mock_settings.REPO_PATH = Path("/some/repo")

            logger = ActionLogger()

            # Mock file operations to ensure they're not called
            with patch("pathlib.Path.open") as mock_file_open:
                logger.log_event("test.event", {"key": "value"})

                mock_file_open.assert_not_called()

    def test_log_event_appends_multiple_entries(self):
        """Test that multiple log_event calls append to the file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_log_path = Path(tmpdir) / "actions.log"

            with patch("shared.action_logger.settings") as mock_settings:
                mock_settings.CORE_ACTION_LOG_PATH = str(test_log_path)
                mock_settings.REPO_PATH = Path(tmpdir)

                logger = ActionLogger()

                # Log multiple events
                logger.log_event("event.1", {"data": "first"})
                logger.log_event("event.2", {"data": "second"})
                logger.log_event("event.3", {"data": "third"})

                with open(test_log_path, encoding="utf-8") as f:
                    lines = f.readlines()

                    assert len(lines) == 3

                    for i, line in enumerate(lines, 1):
                        entry = json.loads(line.strip())
                        assert entry["event_type"] == f"event.{i}"

    def test_log_event_with_complex_details(self):
        """Test that log_event handles complex nested dictionary structures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_log_path = Path(tmpdir) / "actions.log"

            with patch("shared.action_logger.settings") as mock_settings:
                mock_settings.CORE_ACTION_LOG_PATH = str(test_log_path)
                mock_settings.REPO_PATH = Path(tmpdir)

                logger = ActionLogger()

                complex_details = {
                    "nested": {"list": [1, 2, 3], "string": "test", "number": 42.5},
                    "simple": "value",
                    "boolean": True,
                    "null_value": None,
                }

                logger.log_event("complex.event", complex_details)

                with open(test_log_path, encoding="utf-8") as f:
                    content = f.read().strip()
                    log_entry = json.loads(content)

                    assert log_entry["details"] == complex_details

    def test_log_event_handles_file_write_error(self):
        """Test that log_event handles file write errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_log_path = Path(tmpdir) / "actions.log"

            with patch("shared.action_logger.settings") as mock_settings:
                mock_settings.CORE_ACTION_LOG_PATH = str(test_log_path)
                mock_settings.REPO_PATH = Path(tmpdir)

                logger = ActionLogger()

                # Create a read-only file to cause write error
                test_log_path.touch()
                os.chmod(test_log_path, 0o444)

                try:
                    # This should not raise an exception
                    logger.log_event("test.event", {"key": "value"})
                except Exception:
                    pytest.fail(
                        "log_event should not raise exceptions on write failure"
                    )
                finally:
                    # Clean up permissions
                    os.chmod(test_log_path, 0o644)

    def test_log_event_with_empty_details(self):
        """Test that log_event works with empty details dictionary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_log_path = Path(tmpdir) / "actions.log"

            with patch("shared.action_logger.settings") as mock_settings:
                mock_settings.CORE_ACTION_LOG_PATH = str(test_log_path)
                mock_settings.REPO_PATH = Path(tmpdir)

                logger = ActionLogger()

                logger.log_event("empty.event", {})

                with open(test_log_path, encoding="utf-8") as f:
                    content = f.read().strip()
                    log_entry = json.loads(content)

                    assert log_entry["details"] == {}

    def test_log_event_with_dot_notation_event_type(self):
        """Test that log_event accepts dot-notation event types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_log_path = Path(tmpdir) / "actions.log"

            with patch("shared.action_logger.settings") as mock_settings:
                mock_settings.CORE_ACTION_LOG_PATH = str(test_log_path)
                mock_settings.REPO_PATH = Path(tmpdir)

                logger = ActionLogger()

                dot_notation_types = [
                    "crate.processing.started",
                    "user.action.completed",
                    "system.health.check",
                    "deeply.nested.event.type.here",
                ]

                for event_type in dot_notation_types:
                    logger.log_event(event_type, {"test": "data"})

                with open(test_log_path, encoding="utf-8") as f:
                    lines = f.readlines()

                    for i, line in enumerate(lines):
                        entry = json.loads(line.strip())
                        assert entry["event_type"] == dot_notation_types[i]
