from __future__ import annotations

from unittest.mock import MagicMock, patch


# ID: 20eabb37-8e83-4951-b298-d38fc15fb51b
def test_CanaryResultBuilder_build_advisory_failure_result():
    from will.phases.canary import result_builder

    build_advisory_failure_result = getattr(
        result_builder, "build_advisory_failure_result", None
    )
    if build_advisory_failure_result is None:
        import pytest

        pytest.skip("build_advisory_failure_result not present in module")

    test_result = {
        "passed": 3,
        "failed": 2,
        "exit_code": 1,
        "output": "some test output that may be long " * 50,
    }
    test_paths = ["tests/test_example.py", "tests/test_other.py"]
    duration = 1.25

    with patch.object(result_builder, "logger", MagicMock()) as mock_logger:
        result = build_advisory_failure_result(test_result, test_paths, duration)

    assert result.name == "canary_validation"
    assert result.ok is True
    assert result.duration_sec == duration

    data = result.data
    assert data["syntax_valid"] is True
    assert data["logic_preserved"] is True
    assert data["canary_passes"] is False
    assert data["existing_tests_pass"] is False
    assert data["tests_passed"] == 3
    assert data["tests_failed"] == 2
    assert data["exit_code"] == 1
    assert data["test_files"] == test_paths
    assert data["advisory"] is True
    assert "note" in data
    assert len(data["output_preview"]) <= 500
    assert data["output_preview"] == test_result["output"][:500]

    mock_logger.warning.assert_called_once()
    mock_logger.info.assert_called_once()
