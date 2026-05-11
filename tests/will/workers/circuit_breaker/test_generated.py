import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.will.workers.circuit_breaker import (
    CircuitBreakerConfig,
    canonical_signature,
    load_circuit_breaker_config,
    recent_consecutive_identical_count,
    trip,
)


class TestCircuitBreakerConfig:
    """Tests for the CircuitBreakerConfig dataclass."""

    def test_default_values(self):
        """Verify default field values are set correctly."""
        config = CircuitBreakerConfig()
        assert config.threshold_n == 3
        assert config.signature_window_chars == 500
        assert config.max_lookback == 50
        assert config.volatile_patterns == ()

    def test_custom_values(self):
        """Verify custom field values are accepted."""
        patterns = (re.compile(r"\d+"),)
        config = CircuitBreakerConfig(
            threshold_n=5,
            signature_window_chars=300,
            max_lookback=100,
            volatile_patterns=patterns,
        )
        assert config.threshold_n == 5
        assert config.signature_window_chars == 300
        assert config.max_lookback == 100
        assert config.volatile_patterns == patterns

    def test_volatile_patterns_type(self):
        """Verify volatile_patterns is a tuple of compiled patterns."""
        config = CircuitBreakerConfig(volatile_patterns=(re.compile(r"\d+"),))
        assert isinstance(config.volatile_patterns, tuple)
        assert all(isinstance(p, re.Pattern) for p in config.volatile_patterns)


class TestCanonicalSignature:
    """Tests for the canonical_signature function."""

    def test_none_input(self):
        """Verify None collapses to empty string."""
        config = CircuitBreakerConfig()
        result = canonical_signature(None, config)
        assert result == ""

    def test_empty_input(self):
        """Verify empty string collapses to empty string."""
        config = CircuitBreakerConfig()
        result = canonical_signature("", config)
        assert result == ""

    def test_whitespace_collapse(self):
        """Verify runs of whitespace are collapsed to a single space."""
        config = CircuitBreakerConfig()
        result = canonical_signature("error   at   line 42", config)
        # After removing timestamps/UUIDs, whitespace collapsed
        # Expected: "error at line 42"
        assert "  " not in result
        assert result == "error at line 42"

    def test_volatile_pattern_removal(self):
        """Verify substrings matching volatile patterns are stripped."""
        pattern = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\b")
        config = CircuitBreakerConfig(volatile_patterns=(pattern,))
        result = canonical_signature(
            "Timeout at 2024-01-15T10:30:00 for process foo", config
        )
        assert "2024-01-15T10:30:00" not in result
        assert "Timeout at for process foo" in result

    def test_multiple_volatile_patterns(self):
        """Verify multiple patterns are all removed."""
        timestamp_pattern = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\b")
        uuid_pattern = re.compile(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
            re.IGNORECASE,
        )
        config = CircuitBreakerConfig(
            volatile_patterns=(timestamp_pattern, uuid_pattern)
        )
        result = canonical_signature(
            "Error abc12345-1234-1234-1234-123456789abc at 2024-01-15T10:30:00",
            config,
        )
        assert "2024-01-15T10:30:00" not in result
        assert "abc12345-1234-1234-1234-123456789abc" not in result
        assert "Error at" in result

    def test_truncation_to_window_chars(self):
        """Verify long signatures are truncated."""
        config = CircuitBreakerConfig(signature_window_chars=10)
        long_reason = "x" * 100
        result = canonical_signature(long_reason, config)
        assert len(result) == 10
        assert result == "x" * 10

    def test_no_volatile_patterns(self):
        """Verify function works with empty volatile patterns."""
        config = CircuitBreak
