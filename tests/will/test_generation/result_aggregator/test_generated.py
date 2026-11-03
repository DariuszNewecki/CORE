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
