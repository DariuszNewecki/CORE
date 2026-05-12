import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from typing import Any
import re
from dataclasses import dataclass, field

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
        """Verify defaults match fallback constants."""
        config = CircuitBreakerConfig()
        assert config.threshold_n == 3
        assert config.signature_window_chars == 200
        assert config.max_lookback == 10
        assert config.volatile_patterns == ()

    def test_custom_values(self):
        """Verify custom values are stored correctly."""
        pattern = re.compile(r"\d{4}-\d{2}-\d{2}")
        config = CircuitBreakerConfig(
            threshold_n=5,
            signature_window_chars=100,
            max_lookback=20,
            volatile_patterns=(pattern,),
        )
        assert config.threshold_n == 5
        assert config.signature_window_chars == 100
        assert config.max_lookback == 20
        assert config.volatile_patterns == (pattern,)

    def test_volatile_patterns_compiled_regex(self):
        """Verify volatile_patterns contains compiled regex patterns."""
        pattern = re.compile(r"timestamp:\s*\d+")
        config = CircuitBreakerConfig(volatile_patterns=(pattern,))
        assert isinstance(config.volatile_patterns[0], re.Pattern)


class TestCanonicalSignature:
    """Tests for the canonical_signature function."""

    def test_none_input(self):
        """None input should collapse to empty string."""
        config = CircuitBreakerConfig()
        result = canonical_signature(None, config)
        assert result == ""

    def test_empty_string(self):
        """Empty string should remain empty."""
        config = CircuitBreakerConfig()
        result = canonical_signature("", config)
        assert result == ""

    def test_no_volatile_patterns(self):
        """Without patterns, should normalize whitespace and truncate."""
        config = CircuitBreakerConfig(signature_window_chars=50)
        text = "Error: something  went   wrong   here"
        result = canonical_signature(text, config)
        # Collapse whitespace to single spaces
        assert "  " not in result
        assert result == "Error: something went wrong here"

    def test_truncation(self):
        """Should truncate to signature_window_chars."""
        config = CircuitBreakerConfig(signature_window_chars=10)
        long_text = "This is a very long error message that should be truncated"
        result = canonical_signature(long_text, config)
        assert len(result) <= 10
        # Should contain the first 10 chars of the normalized text
        assert result == "This is a "

    def test_volatile_pattern_removal(self):
        """Should strip substrings matching volatile patterns."""
        ts_pattern = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
        config = CircuitBreakerConfig(volatile_patterns=(ts_pattern,))
        text = "Error at 2024-01-15 14:30:00: timeout"
        result = canonical_signature(text, config)
        assert "2024-01-15 14:30:00" not in result
        assert "Error at : timeout" in result or "Error at timeout" in result

    def test_multiple_volatile_patterns(self):
        """Should apply all volatile patterns."""
        ts_pattern = re.compile(r"\d{4}-\d{2}-\d{2}")
        uuid_pattern = re.compile(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}")
        config = CircuitBreakerConfig(volatile_patterns=(ts_pattern, uuid_pattern))
        text = "Failed for 2024-01-15 uuid abcdef12-3456-7890-abcd-ef1234567890"
        result = canonical_signature(text, config)
        assert "2024-01-15" not in result
        assert "abcdef12-3456-7890-abcd-ef1234567890" not in result

    def test_whitespace_only(self):
        """Whitespace-only input should collapse to empty."""
        con
