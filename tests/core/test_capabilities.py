import sys
from unittest.mock import patch

from core.capabilities import introspection


class TestCapabilities:
    """Test suite for core.capabilities module."""

    @patch("core.capabilities.run_poetry_command")
    @patch("core.capabilities.log")
    def test_introspection_success(self, mock_log, mock_run_poetry_command):
        """Test successful introspection cycle with all tools passing."""
        # Arrange
        mock_run_poetry_command.return_value = None  # No exception means success

        # Act
        result = introspection()

        # Assert
        assert result is True
        mock_log.info.assert_any_call("🔍 Starting introspection cycle...")
        mock_log.info.assert_any_call(
            "✅ Knowledge Graph Builder completed successfully."
        )
        mock_log.info.assert_any_call(
            "✅ Constitutional Auditor completed successfully."
        )
        mock_log.info.assert_any_call("🧠 Introspection cycle completed.")

        # Verify both tools were called
        assert mock_run_poetry_command.call_count == 2
        mock_run_poetry_command.assert_any_call(
            "Running Knowledge Graph Builder...",
            ["python", "-m", "system.tools.codegraph_builder"],
        )
        mock_run_poetry_command.assert_any_call(
            "Running Constitutional Auditor...",
            ["python", "-m", "system.governance.constitutional_auditor"],
        )

    @patch("core.capabilities.run_poetry_command")
    @patch("core.capabilities.log")
    def test_introspection_first_tool_fails(self, mock_log, mock_run_poetry_command):
        """Test introspection cycle when first tool fails."""
        # Arrange
        mock_run_poetry_command.side_effect = [
            Exception("First tool failed"),  # First call fails
            None,  # Second call succeeds
        ]

        # Act
        result = introspection()

        # Assert
        assert result is False
        mock_log.error.assert_called_once_with("❌ Knowledge Graph Builder failed.")
        mock_log.info.assert_any_call(
            "✅ Constitutional Auditor completed successfully."
        )
        mock_log.info.assert_any_call("🧠 Introspection cycle completed.")

    @patch("core.capabilities.run_poetry_command")
    @patch("core.capabilities.log")
    def test_introspection_second_tool_fails(self, mock_log, mock_run_poetry_command):
        """Test introspection cycle when second tool fails."""
        # Arrange
        mock_run_poetry_command.side_effect = [
            None,  # First call succeeds
            Exception("Second tool failed"),  # Second call fails
        ]

        # Act
        result = introspection()

        # Assert
        assert result is False
        mock_log.info.assert_any_call(
            "✅ Knowledge Graph Builder completed successfully."
        )
        mock_log.error.assert_called_once_with("❌ Constitutional Auditor failed.")
        mock_log.info.assert_any_call("🧠 Introspection cycle completed.")

    @patch("core.capabilities.run_poetry_command")
    @patch("core.capabilities.log")
    def test_introspection_all_tools_fail(self, mock_log, mock_run_poetry_command):
        """Test introspection cycle when all tools fail."""
        # Arrange
        mock_run_poetry_command.side_effect = Exception("All tools failed")

        # Act
        result = introspection()

        # Assert
        assert result is False
        mock_log.error.assert_any_call("❌ Knowledge Graph Builder failed.")
        mock_log.error.assert_any_call("❌ Constitutional Auditor failed.")
        mock_log.info.assert_any_call("🧠 Introspection cycle completed.")

    @patch("core.capabilities.run_poetry_command")
    @patch("core.capabilities.log")
    def test_introspection_tool_order(self, mock_log, mock_run_poetry_command):
        """Test that tools are executed in the correct order."""
        # Arrange
        mock_run_poetry_command.return_value = None
        call_order = []

        def track_calls(*args, **kwargs):
            call_order.append(args[0])  # args[0] is the description

        mock_run_poetry_command.side_effect = track_calls

        # Act
        introspection()

        # Assert
        expected_calls = [
            "Running Knowledge Graph Builder...",
            "Running Constitutional Auditor...",
        ]
        assert call_order == expected_calls

    @patch("core.capabilities.load_dotenv")
    @patch("core.capabilities.introspection")
    def test_main_success(self, mock_introspection, mock_load_dotenv):
        """Test main execution when introspection succeeds."""
        # Arrange
        mock_introspection.return_value = True

        # Act
        with patch.object(sys, "exit") as mock_exit:
            # Import and execute the main block
            exec(open("src/core/capabilities.py").read())

        # Assert
        mock_load_dotenv.assert_called_once()
        mock_introspection.assert_called_once()
        mock_exit.assert_called_once_with(0)

    @patch("core.capabilities.load_dotenv")
    @patch("core.capabilities.introspection")
    def test_main_failure(self, mock_introspection, mock_load_dotenv):
        """Test main execution when introspection fails."""
        # Arrange
        mock_introspection.return_value = False

        # Act
        with patch.object(sys, "exit") as mock_exit:
            # Import and execute the main block
            exec(open("src/core/capabilities.py").read())

        # Assert
        mock_load_dotenv.assert_called_once()
        mock_introspection.assert_called_once()
        mock_exit.assert_called_once_with(1)

    @patch("core.capabilities.run_poetry_command")
    @patch("core.capabilities.log")
    def test_introspection_exception_handling(self, mock_log, mock_run_poetry_command):
        """Test that exceptions in individual tools are properly caught and logged."""
        # Arrange
        test_exception = RuntimeError("Tool execution failed")
        mock_run_poetry_command.side_effect = test_exception

        # Act
        result = introspection()

        # Assert
        assert result is False
        # Verify both error logs were called
        assert mock_log.error.call_count == 2
        mock_log.error.assert_any_call("❌ Knowledge Graph Builder failed.")
        mock_log.error.assert_any_call("❌ Constitutional Auditor failed.")

    @patch("core.capabilities.run_poetry_command")
    def test_introspection_return_value_consistency(self, mock_run_poetry_command):
        """Test that introspection returns consistent boolean values."""
        # Test successful case
        mock_run_poetry_command.return_value = None
        result = introspection()
        assert result is True
        assert isinstance(result, bool)

        # Test failure case
        mock_run_poetry_command.side_effect = Exception("Failure")
        result = introspection()
        assert result is False
        assert isinstance(result, bool)
