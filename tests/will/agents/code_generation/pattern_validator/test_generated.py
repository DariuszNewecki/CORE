from __future__ import annotations

from unittest.mock import MagicMock

from will.agents.code_generation.pattern_validator import PatternValidator


# ID: ead2b020-a390-43b2-b140-a48a19ff9b8c
def test_PatternValidator_get_pattern_requirements():
    intent_guard = MagicMock()
    validator = PatternValidator(intent_guard)

    result = validator.get_pattern_requirements("pure_function")

    assert isinstance(result, str)
    assert "Pattern Requirements: pure_function" in result
    assert "deterministic" in result
    assert intent_guard is validator.intent_guard
