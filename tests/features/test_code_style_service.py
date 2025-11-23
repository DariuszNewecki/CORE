from unittest.mock import patch

from features.self_healing.code_style_service import format_code


class TestFormatCode:
    """Test suite for format_code function."""

    @patch("features.self_healing.code_style_service.run_poetry_command")
    def test_format_code_with_path(self, mock_run_poetry_command):
        """Test format_code with a specific path."""
        # Given
        test_path = "src/features/some_module.py"

        # When
        format_code(path=test_path)

        # Then
        assert mock_run_poetry_command.call_count == 2

        # Check Black formatting call
        mock_run_poetry_command.assert_any_call(
            f"✨ Formatting {test_path} with Black...", ["black", test_path]
        )

        # Check Ruff formatting call
        mock_run_poetry_command.assert_any_call(
            f"✨ Fixing {test_path} with Ruff...", ["ruff", "check", "--fix", test_path]
        )

    @patch("features.self_healing.code_style_service.run_poetry_command")
    def test_format_code_without_path(self, mock_run_poetry_command):
        """Test format_code without path defaults to src and tests."""
        # Given - no path provided

        # When
        format_code()

        # Then
        assert mock_run_poetry_command.call_count == 2

        # Check Black formatting call with default targets
        mock_run_poetry_command.assert_any_call(
            "✨ Formatting src tests with Black...", ["black", "src", "tests"]
        )

        # Check Ruff formatting call with default targets
        mock_run_poetry_command.assert_any_call(
            "✨ Fixing src tests with Ruff...",
            ["ruff", "check", "--fix", "src", "tests"],
        )

    @patch("features.self_healing.code_style_service.run_poetry_command")
    def test_format_code_with_directory_path(self, mock_run_poetry_command):
        """Test format_code with a directory path."""
        # Given
        directory_path = "src/features"

        # When
        format_code(path=directory_path)

        # Then
        assert mock_run_poetry_command.call_count == 2

        # Check Black formatting call
        mock_run_poetry_command.assert_any_call(
            f"✨ Formatting {directory_path} with Black...", ["black", directory_path]
        )

        # Check Ruff formatting call
        mock_run_poetry_command.assert_any_call(
            f"✨ Fixing {directory_path} with Ruff...",
            ["ruff", "check", "--fix", directory_path],
        )

    @patch("features.self_healing.code_style_service.run_poetry_command")
    def test_format_code_with_empty_string_path(self, mock_run_poetry_command):
        """Test format_code with empty string path."""
        # Given
        empty_path = ""

        # When
        format_code(path=empty_path)

        # Then
        assert mock_run_poetry_command.call_count == 2

        # Check Black formatting call
        mock_run_poetry_command.assert_any_call(
            f"✨ Formatting {empty_path} with Black...", ["black", empty_path]
        )

        # Check Ruff formatting call
        mock_run_poetry_command.assert_any_call(
            f"✨ Fixing {empty_path} with Ruff...",
            ["ruff", "check", "--fix", empty_path],
        )

    @patch("features.self_healing.code_style_service.run_poetry_command")
    def test_format_code_command_order(self, mock_run_poetry_command):
        """Test that Black is called before Ruff."""
        # Given
        test_path = "src/test.py"
        call_order = []

        def track_calls(*args, **kwargs):
            call_order.append(args[0])  # args[0] is the message

        mock_run_poetry_command.side_effect = track_calls

        # When
        format_code(path=test_path)

        # Then
        assert len(call_order) == 2
        assert "Black" in call_order[0]  # First call should be Black
        assert "Ruff" in call_order[1]  # Second call should be Ruff

    @patch("features.self_healing.code_style_service.run_poetry_command")
    def test_format_code_with_none_path(self, mock_run_poetry_command):
        """Test format_code explicitly with None path."""
        # Given
        none_path = None

        # When
        format_code(path=none_path)

        # Then
        assert mock_run_poetry_command.call_count == 2

        # Should use default targets
        mock_run_poetry_command.assert_any_call(
            "✨ Formatting src tests with Black...", ["black", "src", "tests"]
        )

        mock_run_poetry_command.assert_any_call(
            "✨ Fixing src tests with Ruff...",
            ["ruff", "check", "--fix", "src", "tests"],
        )
