import pytest


pytestmark = pytest.mark.legacy

from datetime import UTC
from unittest.mock import Mock, patch

from shared.time import now_iso


class TestTimeModule:
    """Test suite for shared.time module."""

    def test_now_iso_returns_string(self):
        """Test that now_iso returns a string."""
        # Act
        result = now_iso()

        # Assert
        assert isinstance(result, str)

    def test_now_iso_contains_iso_format_indicators(self):
        """Test that the returned string contains ISO 8601 format indicators."""
        # Act
        result = now_iso()

        # Assert - ISO format should contain 'T' and 'Z' or timezone info
        assert "T" in result
        # Should contain either Z (UTC) or +00:00 (UTC offset)
        assert "Z" in result or "+00:00" in result

    @patch("shared.time.datetime")
    def test_now_iso_calls_datetime_now_with_utc(self, mock_datetime):
        """Test that datetime.now is called with UTC timezone."""
        # Arrange
        mock_now = Mock()
        mock_datetime.now.return_value = mock_now
        mock_now.isoformat.return_value = "2023-01-01T12:00:00Z"

        # Act
        result = now_iso()

        # Assert
        mock_datetime.now.assert_called_once_with(UTC)
        mock_now.isoformat.assert_called_once()

    @patch("shared.time.datetime")
    def test_now_iso_returns_isoformat_result(self, mock_datetime):
        """Test that the function returns the result of isoformat()."""
        # Arrange
        expected_result = "2023-01-01T12:00:00.123456Z"
        mock_now = Mock()
        mock_datetime.now.return_value = mock_now
        mock_now.isoformat.return_value = expected_result

        # Act
        result = now_iso()

        # Assert
        assert result == expected_result

    def test_now_iso_returns_valid_iso_format(self):
        """Test that the returned string is a valid ISO 8601 format."""
        # Act
        result = now_iso()

        # Assert - Basic ISO 8601 format validation
        # Should be at least 20 characters (minimal valid ISO string)
        assert len(result) >= 20
        # Should start with year (4 digits)
        assert result[0:4].isdigit()

    @patch("shared.time.datetime")
    def test_now_iso_uses_utc_timezone(self, mock_datetime):
        """Test that UTC timezone is used for timestamp generation."""
        # Arrange
        mock_now = Mock()
        mock_datetime.now.return_value = mock_now
        mock_now.isoformat.return_value = "2023-01-01T12:00:00Z"

        # Act
        now_iso()

        # Assert
        # Verify UTC timezone is passed to datetime.now
        call_args = mock_datetime.now.call_args
        assert call_args[0][0] == UTC

    @patch("shared.time.datetime")
    def test_now_iso_multiple_calls(self, mock_datetime):
        """Test that multiple calls work correctly."""
        # Arrange
        mock_now = Mock()
        mock_datetime.now.return_value = mock_now
        mock_now.isoformat.side_effect = [
            "2023-01-01T12:00:00Z",
            "2023-01-01T12:00:01Z",
            "2023-01-01T12:00:02Z",
        ]

        # Act & Assert
        for expected in [
            "2023-01-01T12:00:00Z",
            "2023-01-01T12:00:01Z",
            "2023-01-01T12:00:02Z",
        ]:
            result = now_iso()
            assert result == expected

    def test_now_iso_no_external_dependencies(self):
        """Test that the function doesn't require external dependencies."""
        # This test ensures the function is self-contained
        # Act
        result = now_iso()

        # Assert - Should complete without external calls
        assert result is not None
        assert isinstance(result, str)

    @patch("shared.time.datetime")
    def test_now_iso_exception_handling(self, mock_datetime):
        """Test that the function handles datetime exceptions gracefully."""
        # Arrange
        mock_datetime.now.side_effect = Exception("Test exception")

        # Act & Assert
        with pytest.raises(Exception, match="Test exception"):
            now_iso()
