"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/utils/common_knowledge.py
- Symbol: get_deterministic_id
- Status: verified_in_sandbox
- Generated: 2026-01-07 20:41:35
"""

# Detected return type: int (positive signed 64-bit integer in range [0, 2^63 - 1])

import hashlib

from shared.utils.common_knowledge import get_deterministic_id


def test_get_deterministic_id_basic():
    """Test basic deterministic ID generation."""
    text = "Hello world"
    result1 = get_deterministic_id(text)
    result2 = get_deterministic_id(text)

    assert result1 == result2
    assert isinstance(result1, int)
    assert 0 <= result1 < 2**63


def test_get_deterministic_id_different_texts():
    """Different texts should produce different IDs (with high probability)."""
    id1 = get_deterministic_id("Hello")
    id2 = get_deterministic_id("World")
    id3 = get_deterministic_id("Hello World")

    # While collisions are possible, they're extremely unlikely with SHA-256
    assert id1 != id2
    assert id1 != id3
    assert id2 != id3


def test_get_deterministic_id_empty_string():
    """Empty string should produce a valid deterministic ID."""
    result = get_deterministic_id("")
    assert isinstance(result, int)
    assert 0 <= result < 2**63

    # Verify it's deterministic
    assert result == get_deterministic_id("")


def test_get_deterministic_id_special_characters():
    """Test with special characters and Unicode."""
    test_cases = [
        "Hello…World",  # Unicode ellipsis
        "Café",
        "🎯",
        "Line1\nLine2",
        "   leading/trailing spaces   ",
        "a" * 1000,  # Long string
    ]

    for text in test_cases:
        result = get_deterministic_id(text)
        assert isinstance(result, int)
        assert 0 <= result < 2**63
        # Verify determinism
        assert result == get_deterministic_id(text)


def test_get_deterministic_id_range():
    """Verify IDs are always in the safe range for Qdrant/Postgres."""
    # Test with various inputs to ensure range constraint
    test_texts = [
        "",
        "a",
        "A very long string " * 100,
        "Special chars: !@#$%^&*()",
        "Unicode: αβγδε",
    ]

    for text in test_texts:
        result = get_deterministic_id(text)
        assert 0 <= result < 2**63, f"Failed for text: {text[:50]}..."


def test_get_deterministic_id_consistent_with_sha256():
    """Verify the implementation matches the described algorithm."""
    test_text = "Test deterministic ID generation"

    # Manual calculation
    hex_hash = hashlib.sha256(test_text.encode("utf-8")).hexdigest()
    first_16_chars = hex_hash[:16]
    expected = int(first_16_chars, 16) % (2**63)

    result = get_deterministic_id(test_text)
    assert result == expected


def test_get_deterministic_id_case_sensitive():
    """Verify case sensitivity."""
    id_lower = get_deterministic_id("hello")
    id_upper = get_deterministic_id("HELLO")
    id_mixed = get_deterministic_id("Hello")

    assert id_lower != id_upper
    assert id_lower != id_mixed
    assert id_upper != id_mixed


def test_get_deterministic_id_whitespace():
    """Verify whitespace affects the hash."""
    id1 = get_deterministic_id("hello world")
    id2 = get_deterministic_id("helloworld")
    id3 = get_deterministic_id(" hello world ")

    assert id1 != id2
    assert id1 != id3
    assert id2 != id3


def test_get_deterministic_id_encoding():
    """Verify UTF-8 encoding is used consistently."""
    # These would produce different results with different encodings
    text = "café"
    result1 = get_deterministic_id(text)

    # Should match manual UTF-8 encoding
    hex_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    expected = int(hex_hash[:16], 16) % (2**63)

    assert result1 == expected


def test_get_deterministic_id_positive_only():
    """Verify all results are positive (mod operation ensures this)."""
    # Test many random strings to ensure positivity
    import random
    import string

    for _ in range(100):
        random_text = "".join(
            random.choices(string.ascii_letters + string.digits, k=50)
        )
        result = get_deterministic_id(random_text)
        assert result >= 0
