"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/utils/common_knowledge.py
- Symbol: get_deterministic_id
- Status: verified_in_sandbox
- Generated: 2026-01-07 22:13:56
"""

from shared.utils.common_knowledge import get_deterministic_id


# Detected return type: int (64-bit unsigned, safe for Qdrant/Postgres)


def test_get_deterministic_id_returns_int():
    """Basic test to ensure the function returns an integer."""
    result = get_deterministic_id("test string")
    assert isinstance(result, int)


def test_get_deterministic_id_deterministic():
    """Same input must always produce the same output."""
    text = "A deterministic input string"
    result1 = get_deterministic_id(text)
    result2 = get_deterministic_id(text)
    assert result1 == result2


def test_get_deterministic_id_different_inputs():
    """Different inputs should (very likely) produce different IDs."""
    result1 = get_deterministic_id("first")
    result2 = get_deterministic_id("second")
    assert result1 != result2


def test_get_deterministic_id_empty_string():
    """Function should handle empty string input."""
    result = get_deterministic_id("")
    assert isinstance(result, int)
    # Ensure it's deterministic for empty string as well
    assert result == get_deterministic_id("")


def test_get_deterministic_id_range():
    """Output must be within the positive signed 64-bit integer range [0, 2^63 - 1]."""
    test_strings = ["", "a", "hello world", "unicode: café and café", "a" * 1000]
    for text in test_strings:
        result = get_deterministic_id(text)
        assert 0 <= result < 2**63


def test_get_deterministic_id_unicode():
    """Function should handle Unicode characters correctly and deterministically."""
    text1 = "café"
    text2 = "cafe\u0301"  # 'e' with combining acute accent
    # These are different Unicode strings, so they should produce different IDs
    result1 = get_deterministic_id(text1)
    result2 = get_deterministic_id(text2)
    assert result1 != result2
    # Each should be deterministic
    assert result1 == get_deterministic_id(text1)
    assert result2 == get_deterministic_id(text2)


def test_get_deterministic_id_whitespace():
    """Whitespace characters should affect the hash."""
    result1 = get_deterministic_id("hello world")
    result2 = get_deterministic_id("helloworld")
    result3 = get_deterministic_id("hello  world")  # double space
    assert result1 != result2
    assert result1 != result3
    assert result2 != result3


def test_get_deterministic_id_case_sensitive():
    """Function should be case-sensitive."""
    result_lower = get_deterministic_id("hello")
    result_upper = get_deterministic_id("HELLO")
    result_mixed = get_deterministic_id("Hello")
    assert result_lower != result_upper
    assert result_lower != result_mixed
    assert result_upper != result_mixed
