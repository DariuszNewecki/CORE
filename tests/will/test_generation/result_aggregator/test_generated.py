from __future__ import annotations

from unittest.mock import MagicMock, patch

from will.test_generation.result_aggregator import TestResultAggregator


# ID: b46b16cf-06ae-4fea-815a-85f0500f96cb
def test_TestResultAggregator_format_summary_json():
    result = MagicMock()
    result.file_path = "src/will/example.py"
    result.total_symbols = 4
    result.tests_generated = 4
    result.sandbox_passed = 3
    result.tests_failed = 1
    result.tests_skipped = 0
    result.success_rate = 0.75

    harness = MagicMock()
    harness.has_db_harness = True

    with patch("will.test_generation.result_aggregator.time") as mock_time:
        mock_time.strftime.return_value = "2024-01-01 12:00:00"

        summary = TestResultAggregator.format_summary_json(
            result, "/tmp/session", harness
        )

    assert summary == {
        "file_path": "src/will/example.py",
        "total_symbols": 4,
        "stats": {
            "validated": 4,
            "passed": 3,
            "failed": 1,
            "skipped": 0,
        },
        "validated_rate": "75.0%",
        "artifacts_location": "/tmp/session",
        "harness_detected": True,
        "timestamp": "2024-01-01 12:00:00",
    }





# ID: 2dc61f29-409c-44df-b607-7d448929f78e
def test_TestResultAggregator_build_final_result():
    file_path = "src/example/module.py"
    attempts = [
        {"validated": True, "sandbox_passed": True, "sandbox_ran": True},
        {"validated": True, "sandbox_passed": False, "sandbox_ran": True},
        {"validated": False, "skipped": True},
        {"validated": False, "validation_failure": True},
    ]
    start_time = 1000.0
    switches = 2
    patterns = {"pattern_a": 3}

    with patch(
        "will.test_generation.result_aggregator.time.time",
        return_value=1010.0,
    ):
        result = TestResultAggregator.build_final_result(
            file_path=file_path,
            attempts=attempts,
            start_time=start_time,
            switches=switches,
            patterns=patterns,
        )

    assert result.file_path == file_path
    assert result.total_symbols == 4
    assert result.tests_generated == 2
    assert result.tests_failed == 1
    assert result.tests_skipped == 1
    assert result.success_rate == 2 / 4
    assert result.strategy_switches == switches
    assert result.patterns_learned == patterns
    assert result.total_duration == 10.0
    assert result.generated_tests == attempts
    assert result.validation_failures == 1
    assert result.sandbox_passed == 1
