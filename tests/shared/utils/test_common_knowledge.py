# tests/shared/utils/test_common_knowledge.py
from src.shared.utils.common_knowledge import action_name, normalize_text, sanitize_key


class TestActionName:
    """Tests for action_name function."""

    def test_action_name_returns_string(self):
        """Test that action_name returns a string."""
        result = action_name()
        assert isinstance(result, str)
        assert result == "action_name"


class TestSanitizeKey:
    """Tests for sanitize_key function."""

    def test_sanitize_key_lowercases(self):
        """Test that sanitize_key converts to lowercase."""
        result = sanitize_key("UPPERCASE")
        assert result == "uppercase"

    def test_sanitize_key_replaces_special_chars_with_underscore(self):
        """Test that special characters are replaced with underscores."""
        result = sanitize_key("key-with-special@chars!")
        assert result == "key_with_special_chars_"

    def test_sanitize_key_preserves_alphanumeric(self):
        """Test that alphanumeric characters are preserved."""
        result = sanitize_key("key123")
        assert result == "key123"

    def test_sanitize_key_handles_mixed_case(self):
        """Test that mixed case is handled correctly."""
        result = sanitize_key("MixedCase-Key@Name")
        assert result == "mixedcase_key_name"

    def test_sanitize_key_handles_multiple_special_chars(self):
        """Test that multiple consecutive special chars become one underscore."""
        result = sanitize_key("key@@@name!!!")
        assert result == "key_name_"

    def test_sanitize_key_handles_spaces(self):
        """Test that spaces are replaced with underscores."""
        result = sanitize_key("key with spaces")
        assert result == "key_with_spaces"

    def test_sanitize_key_empty_string(self):
        """Test that empty string returns empty string."""
        result = sanitize_key("")
        assert result == ""


class TestNormalizeText:
    """Tests for normalize_text function."""

    def test_normalize_text_collapses_whitespace(self):
        """Test that multiple whitespace characters are collapsed."""
        result = normalize_text("text   with    multiple   spaces")
        assert result == "text with multiple spaces"

    def test_normalize_text_strips_whitespace(self):
        """Test that leading and trailing whitespace is removed."""
        result = normalize_text("   text with spaces   ")
        assert result == "text with spaces"

    def test_normalize_text_handles_tabs_and_newlines(self):
        """Test that tabs and newlines are collapsed to single spaces."""
        result = normalize_text("text\twith\nmultiple\n\twhitespace")
        assert result == "text with multiple whitespace"

    def test_normalize_text_empty_string(self):
        """Test that empty string returns empty string."""
        result = normalize_text("")
        assert result == ""

    def test_normalize_text_only_whitespace(self):
        """Test that string with only whitespace returns empty string."""
        result = normalize_text("   \t\n   ")
        assert result == ""

    def test_normalize_text_preserves_single_spaces(self):
        """Test that single spaces are preserved."""
        result = normalize_text("text with single spaces")
        assert result == "text with single spaces"
