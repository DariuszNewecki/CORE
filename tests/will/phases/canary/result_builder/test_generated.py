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


from will.phases.canary.result_builder import CanaryResultBuilder


# ID: 8d2ce28c-7bc4-4e51-9ff0-5a04bab9ede0
def test_CanaryResultBuilder_build_success_result():
    test_result = {
        "passed": 10,
        "failed": 0,
        "exit_code": 0,
    }
    test_paths = ["tests/test_a.py", "tests/test_b.py"]
    duration = 3.5

    builder = CanaryResultBuilder()

    result = builder.build_success_result(test_result, test_paths, duration)

    assert result.name == "canary_validation"
    assert result.ok is True
    assert result.duration_sec == duration
    assert result.data["syntax_valid"] is True
    assert result.data["logic_preserved"] is True
    assert result.data["canary_passes"] is True
    assert result.data["existing_tests_pass"] is True
    assert result.data["tests_passed"] == 10
    assert result.data["tests_failed"] == 0
    assert result.data["exit_code"] == 0
    assert result.data["test_files"] == test_paths
    assert result.data["advisory"] is False


# ID: f9eab38d-12b8-4a21-a0e0-61d527c4d416
def test_CanaryResultBuilder_build_no_tests_result() -> None:
    builder = CanaryResultBuilder()
    with patch("will.phases.canary.result_builder.logger") as mock_logger:
        result = builder.build_no_tests_result(duration=1.5)

    assert result.name == "canary_validation"
    assert result.ok is True
    assert result.duration_sec == 1.5
    assert result.data == {
        "syntax_valid": True,
        "logic_preserved": True,
        "canary_passes": True,
        "existing_tests_pass": True,
        "tests_found": 0,
        "note": "No existing tests - behavioral preservation cannot be verified",
    }
    mock_logger.info.assert_called_once()


# ID: 0bed3de9-1646-440a-8f72-30bf59a5c4c7
def test_build_skipped_result():
    result = CanaryResultBuilder.build_skipped_result("no changes detected", 1.5)

    assert result.name == "canary_validation"
    assert result.ok is True
    assert result.duration_sec == 1.5
    assert result.data["skipped"] is True
    assert result.data["reason"] == "no changes detected"
    assert result.data["syntax_valid"] is True
    assert result.data["logic_preserved"] is True
    assert result.data["canary_passes"] is True
    assert result.data["existing_tests_pass"] is True





# ID: d2320bd3-4516-4e3b-9513-6602eb4676c0
def test_CanaryResultBuilder():
    test_result = {
        "passed": 5,
        "failed": 0,
        "exit_code": 0,
        "output": "all good",
    }
    with patch("will.phases.canary.result_builder.logger"):
        result = CanaryResultBuilder.build_success_result(
            test_result, ["tests/test_a.py"], 1.25
        )

    assert result.name == "canary_validation"
    assert result.ok is True
    assert result.duration_sec == 1.25
    assert result.data["canary_passes"] is True
    assert result.data["existing_tests_pass"] is True
    assert result.data["tests_passed"] == 5
    assert result.data["tests_failed"] == 0
    assert result.data["test_files"] == ["tests/test_a.py"]
    assert result.data["advisory"] is False
