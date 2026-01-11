"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/cli_types.py
- Symbol: CommandResult
- Status: verified_in_sandbox
- Generated: 2026-01-11 00:54:51
"""

import pytest
from shared.cli_types import CommandResult

# CommandResult is a synchronous class (not async def __init__ or __post_init__)
# All tests will use regular def test_... functions

def test_command_result_initialization():
    """Test basic initialization with required fields"""
    result = CommandResult(name="test.command", ok=True, data={"count": 5})

    assert result.name == "test.command"
    assert result.ok == True
    assert result.data == {"count": 5}
    assert result.duration_sec == 0.0
    assert result.logs == []

def test_command_result_with_optional_fields():
    """Test initialization with all optional fields"""
    result = CommandResult(
        name="sync.knowledge",
        ok=False,
        data={"synced": 3, "failed": 2},
        duration_sec=1.5,
        logs=["Starting sync", "Processing items", "Sync completed"]
    )

    assert result.name == "sync.knowledge"
    assert result.ok == False
    assert result.data == {"synced": 3, "failed": 2}
    assert result.duration_sec == 1.5
    assert result.logs == ["Starting sync", "Processing items", "Sync completed"]

def test_command_result_name_validation_empty():
    """Test that empty name raises ValueError"""
    with pytest.raises(ValueError, match="CommandResult.name must be non-empty string"):
        CommandResult(name="", ok=True, data={})

def test_command_result_name_validation_non_string():
    """Test that non-string name raises ValueError"""
    with pytest.raises(ValueError, match="CommandResult.name must be non-empty string"):
        CommandResult(name=123, ok=True, data={})

def test_command_result_data_validation_non_dict():
    """Test that non-dict data raises ValueError"""
    with pytest.raises(ValueError, match="CommandResult.data must be a dict"):
        CommandResult(name="test.command", ok=True, data="not a dict")

def test_command_result_data_validation_list():
    """Test that list data raises ValueError"""
    with pytest.raises(ValueError, match="CommandResult.data must be a dict"):
        CommandResult(name="test.command", ok=True, data=["item1", "item2"])

def test_command_result_data_validation_none():
    """Test that None data raises ValueError"""
    with pytest.raises(ValueError, match="CommandResult.data must be a dict"):
        CommandResult(name="test.command", ok=True, data=None)

def test_command_result_complex_data():
    """Test with complex nested data structures"""
    complex_data = {
        "items": [{"id": 1, "name": "test"}, {"id": 2, "name": "test2"}],
        "metadata": {"version": "1.0", "timestamp": "2024-01-01"},
        "counts": {"total": 100, "processed": 95, "failed": 5}
    }

    result = CommandResult(
        name="fix.ids",
        ok=True,
        data=complex_data
    )

    assert result.name == "fix.ids"
    assert result.ok == True
    assert result.data == complex_data

def test_command_result_default_logs_mutation():
    """Test that default logs list is not shared between instances"""
    result1 = CommandResult(name="cmd1", ok=True, data={})
    result2 = CommandResult(name="cmd2", ok=True, data={})

    result1.logs.append("log for result1")

    assert result1.logs == ["log for result1"]
    assert result2.logs == []

def test_command_result_zero_duration():
    """Test that duration_sec defaults to 0.0"""
    result = CommandResult(name="test.command", ok=True, data={})
    assert result.duration_sec == 0.0

def test_command_result_negative_duration():
    """Test that negative duration is allowed (edge case)"""
    result = CommandResult(
        name="test.command",
        ok=True,
        data={},
        duration_sec=-0.5
    )
    assert result.duration_sec == -0.5

def test_command_result_boolean_ok_values():
    """Test both boolean values for ok field"""
    result_true = CommandResult(name="success.cmd", ok=True, data={"result": "success"})
    result_false = CommandResult(name="failure.cmd", ok=False, data={"error": "failed"})

    assert result_true.ok == True
    assert result_false.ok == False

def test_command_result_empty_dict_data():
    """Test with empty dict as data"""
    result = CommandResult(name="empty.cmd", ok=True, data={})
    assert result.data == {}

def test_command_result_name_with_dots():
    """Test name with dot notation"""
    result = CommandResult(name="module.submodule.command", ok=True, data={"status": "ok"})
    assert result.name == "module.submodule.command"

def test_command_result_name_with_hyphens():
    """Test name with hyphens"""
    result = CommandResult(name="fix-data-ids", ok=True, data={"fixed": 10})
    assert result.name == "fix-data-ids"

def test_command_result_logs_as_empty_list():
    """Test explicit empty logs list"""
    result = CommandResult(
        name="test.command",
        ok=True,
        data={},
        logs=[]
    )
    assert result.logs == []

def test_command_result_multiple_log_entries():
    """Test with multiple log entries including special characters"""
    logs = [
        "INFO: Starting process",
        "WARNING: Deprecated API used",
        "ERROR: Failed to connect to database",
        "DEBUG: Retry attempt 3"
    ]

    result = CommandResult(
        name="process.data",
        ok=False,
        data={"attempts": 3},
        logs=logs
    )

    assert result.logs == logs
    assert len(result.logs) == 4
