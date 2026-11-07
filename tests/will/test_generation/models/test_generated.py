from __future__ import annotations

from will.test_generation.models import TestGenerationResult


# ID: 457f950d-41fa-47a3-8928-c89c65a1acdc
def test_TestGenerationResult():
    result = TestGenerationResult(
        file_path="src/will/example.py",
        total_symbols=10,
        tests_generated=8,
        tests_failed=1,
        tests_skipped=1,
        success_rate=0.8,
        strategy_switches=2,
        patterns_learned={"pattern_a": 3},
        total_duration=1.23,
    )

    assert result.file_path == "src/will/example.py"
    assert result.total_symbols == 10
    assert result.tests_generated == 8
    assert result.tests_failed == 1
    assert result.tests_skipped == 1
    assert result.success_rate == 0.8
    assert result.strategy_switches == 2
    assert result.patterns_learned == {"pattern_a": 3}
    assert result.total_duration == 1.23
    assert result.generated_tests == []
    assert result.validation_failures == 0
    assert result.sandbox_passed == 0
