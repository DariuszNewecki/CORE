"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/logger.py
- Symbol: JsonFormatter
- Status: 8 tests passed, some failed
- Passing tests: test_json_formatter_basic_log_record, test_json_formatter_with_exception, test_json_formatter_custom_attributes, test_json_formatter_activity_attribute, test_json_formatter_standard_attrs_excluded, test_json_formatter_timestamp_format, test_json_formatter_different_log_levels, test_json_formatter_valid_json_output
- Generated: 2026-01-11 01:07:02
"""

import json
import logging
import sys
from datetime import datetime

from shared.logger import JsonFormatter


def test_json_formatter_basic_log_record():
    """Test basic log record formatting."""
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="/test/path.py",
        lineno=42,
        msg="Test message %s",
        args=("arg1",),
        exc_info=None,
        func="test_function",
        sinfo=None,
    )
    result = formatter.format(record)
    parsed = json.loads(result)
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "Test message arg1"
    assert parsed["logger"] == "test_logger"
    assert parsed["module"] == "path"
    assert parsed["line"] == 42
    assert "timestamp" in parsed
    assert "run_id" not in parsed
    assert "exception" not in parsed


def test_json_formatter_with_exception():
    """Test log record with exception information."""
    formatter = JsonFormatter()
    try:
        raise ValueError("Test error")
    except ValueError:
        exc_info = sys.exc_info()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.ERROR,
        pathname="/test/path.py",
        lineno=42,
        msg="Error occurred",
        args=(),
        exc_info=exc_info,
        func="test_function",
        sinfo=None,
    )
    result = formatter.format(record)
    parsed = json.loads(result)
    assert parsed["level"] == "ERROR"
    assert parsed["message"] == "Error occurred"
    assert "exception" in parsed
    assert "ValueError" in parsed["exception"]
    assert "Test error" in parsed["exception"]


def test_json_formatter_custom_attributes():
    """Test log record with custom attributes."""
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="/test/path.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
        func="test_function",
        sinfo=None,
    )
    record.custom_field = "custom_value"
    record.another_field = {"nested": "value"}
    result = formatter.format(record)
    parsed = json.loads(result)
    assert parsed["custom_field"] == "custom_value"
    assert parsed["another_field"] == {"nested": "value"}


def test_json_formatter_activity_attribute():
    """Test log record with activity attribute."""
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="/test/path.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
        func="test_function",
        sinfo=None,
    )
    record.activity = "test_activity"
    result = formatter.format(record)
    parsed = json.loads(result)
    assert parsed["activity"] == "test_activity"


def test_json_formatter_standard_attrs_excluded():
    """Test that standard logging attributes are excluded from custom fields."""
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="/test/path.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
        func="test_function",
        sinfo=None,
    )
    result = formatter.format(record)
    parsed = json.loads(result)
    standard_keys = {
        "name",
        "msg",
        "args",
        "levelname",
        "pathname",
        "filename",
        "exc_info",
        "lineno",
        "funcName",
        "created",
    }
    for key in standard_keys:
        assert key not in parsed or key in {"level", "message", "module", "line"}


def test_json_formatter_timestamp_format():
    """Test that timestamp is in ISO format with timezone."""
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="/test/path.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
        func="test_function",
        sinfo=None,
    )
    result = formatter.format(record)
    parsed = json.loads(result)
    timestamp = parsed["timestamp"]
    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    assert dt.tzinfo is not None


def test_json_formatter_different_log_levels():
    """Test formatter with different log levels."""
    formatter = JsonFormatter()
    for level_name, level_num in [
        ("DEBUG", 10),
        ("INFO", 20),
        ("WARNING", 30),
        ("ERROR", 40),
        ("CRITICAL", 50),
    ]:
        record = logging.LogRecord(
            name="test_logger",
            level=level_num,
            pathname="/test/path.py",
            lineno=42,
            msg=f"{level_name} message",
            args=(),
            exc_info=None,
            func="test_function",
            sinfo=None,
        )
        result = formatter.format(record)
        parsed = json.loads(result)
        assert parsed["level"] == level_name
        assert parsed["message"] == f"{level_name} message"


def test_json_formatter_valid_json_output():
    """Test that output is always valid JSON."""
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="/test/path.py",
        lineno=42,
        msg='Message with "quotes" and \n newline',
        args=(),
        exc_info=None,
        func="test_function",
        sinfo=None,
    )
    result = formatter.format(record)
    parsed = json.loads(result)
    assert isinstance(parsed, dict)
    assert "message" in parsed
