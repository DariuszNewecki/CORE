"""
Tests for audit_violation_filter module.

Covers filter_actionable_violations public function with happy paths,
error paths, and edge cases.
"""

import logging
from unittest.mock import patch

import pytest

from will.workers.audit_violation_filter import filter_actionable_violations


SENTINEL_STDIN = "/dev/stdin"
SENTINEL_NULL = "/dev/null"


# ID: 57699b47-8c44-4f4a-9b0d-cd4df7c52135
def test_empty_list_returns_empty():
    """An empty violations list should return an empty list."""
    result = filter_actionable_violations([])
    assert result == []


# ID: 9d4e8eb8-3e7b-44cc-a3f6-629f3d136fb5
def test_actionable_violation_preserved():
    """A normal Python file violation that passes all checks should be returned."""
    violation = {
        "file_path": "src/main.py",
        "rule_id": "quality.no_dead_code",
        "message": "Dead code found",
    }
    result = filter_actionable_violations([violation])
    assert result == [violation]


# ID: d9659312-2592-42dc-9fe4-8f6f5f9d00e1
def test_multiple_actionable_violations_preserved():
    """Multiple valid violations should all be returned."""
    violations = [
        {"file_path": "src/module.py", "rule_id": "quality.no_dead_code", "message": "msg1"},
        {"file_path": "src/utils.py", "rule_id": "purity.pure_function", "message": "msg2"},
        {"file_path": "tests/test_utils.py", "rule_id": "style.naming", "message": "msg3"},
    ]
    result = filter_actionable_violations(violations)
    assert result == violations


# ID: 22c59dea-a4b8-4e44-a893-92039a5b45a0
def test_sentinel_stdin_dropped():
    """Violations with /dev/stdin file_path should be filtered out."""
    violation = {"file_path": SENTINEL_STDIN, "rule_id": "quality.no_dead_code"}
    result = filter_actionable_violations([violation])
    assert result == []


# ID: 66cc2926-b9eb-4e31-856d-1991fe4ad641
def test_sentinel_null_dropped():
    """Violations with /dev/null file_path should be filtered out."""
    violation = {"file_path": SENTINEL_NULL, "rule_id": "quality.no_dead_code"}
    result = filter_actionable_violations([violation])
    assert result == []


# ID: e54e348c-02db-4e6a-9602-8388cff1551d
def test_symbol_pair_path_dropped():
    """Violations with file_path starting with __symbol_pair__ should be filtered out."""
    violation = {
        "file_path": "__symbol_pair__some_data.py",
        "rule_id": "quality.no_dead_code",
    }
    result = filter_actionable_violations([violation])
    assert result == []


# ID: a227174c-cd23-4543-9a05-b8913e991b04
def test_non_python_file_dropped():
    """Violations with non-.py extension should be filtered out."""
    violation = {
        "file_path": "src/data.json",
        "rule_id": "quality.no_dead_code",
    }
    result = filter_actionable_violations([violation])
    assert result == []


# ID: 5f622661-4569-42d4-a3cc-b08372638e26
def test_no_extension_file_dropped():
    """Violations with no file extension should be filtered out."""
    violation = {
        "file_path": "Makefile",
        "rule_id": "quality.no_dead_code",
    }
    result = filter_actionable_violations([violation])
    assert result == []


# ID: 5fa8b465-31f2-4aac-b0ee-cc18e050a963
def test_malformed_rule_id_with_slash_dropped():
    """Violations with rule_id containing '/' should be filtered out."""
    violation = {
        "file_path": "src/main.py",
        "rule_id": "enforcement/mappings/arch/foo.yaml",
    }
    result = filter_actionable_violations([violation])
    assert result == []


# ID: bd3bca05-5768-48dd-9d76-6cabb9a5f972
def test_missing_file_path_uses_empty_string():
    """When file_path is missing, it defaults to empty string and is not dropped by sentinel or Python check."""
    violation = {"rule_id": "quality.no_dead_code"}
    result = filter_actionable_violations([violation])
    # Empty string doesn't match sentinels, doesn't start with __symbol_pair__,
    # doesn't end with .py, so it should be dropped for non-Python
    assert result == []


# ID: 89e3e8d7-17cf-4d19-bfc6-ff1a916143d5
def test_missing_rule_id_uses_empty_string():
    """When rule_id is missing, it defaults to empty string without slash."""
    violation = {"file_path": "src/main.py"}
    result = filter_actionable_violations([violation])
    assert result == [violation]


# ID: c71049de-77c3-42aa-92d3-3427cf2b5ede
def test_none_file_path_treated_as_empty():
    """When file_path is None, it should be treated as empty string."""
    violation = {"file_path": None, "rule_id": "quality.no_dead_code"}
    result = filter_actionable_violations([violation])
    assert result == []


# ID: df2139a7-27a4-4785-a31c-2079bd7dc138
def test_none_rule_id_treated_as_empty():
    """When rule_id is None, it should be treated as empty string."""
    violation = {"file_path": "src/main.py", "rule_id": None}
    result = filter_actionable_violations([violation])
    assert result == [violation]


# ID: 7e158856-7035-4775-ba34-dd16157082da
def test_mixed_actionable_and_non_actionable():
    """Mix of valid and invalid violations, only valid ones returned."""
    violations = [
        {"file_path": "src/main.py", "rule_id": "quality.no_dead_code"},
        {"file_path": SENTINEL_STDIN, "rule_id": "quality.no_dead_code"},
        {"file_path": "src/data.json", "rule_id": "quality.no_dead_code"},
        {"file_path": "__symbol_pair__data.py", "rule_id": "quality.no_dead_code"},
        {"file_path": "src/utils.py", "rule_id": "style.naming"},
    ]
    result = filter_actionable_violations(violations)
    assert len(result) == 2
    assert result[0] == violations[0]
    assert result[1] == violations[4]


# ID: 2e84ba0f-7ad2-4a02-bd33-84ba90e84de3
def test_file_path_with_py_but_slash_in_directory():
    """file_path with .py extension and proper rule_id should pass even if path contains slashes in middle."""
    violation = {
        "file_path": "src/utils/helpers.py",
        "rule_id": "quality.no_dead_code",
    }
    result = filter_actionable_violations([violation])
    assert result == [violation]


@patch("will.workers.audit_violation_filter.logger")
# ID: ff5b9fa4-53f3-46cb-b66f-4835342d6534
def test_dropped_violation_logged_at_debug(mock_logger):
    """When a sentinel violation is dropped, logger.debug should be called."""
    violation = {"file_path": SENTINEL_STDIN, "rule_id": "quality.no_dead_code"}
    filter_actionable_violations([violation])
    mock_logger.debug.assert_called_once()


@patch("will.workers.audit_violation_filter.logger")
# ID: 722232a2-f47b-4f1c-a5a5-e164e57271e0
def test_non_python_file_logged_at_debug(mock_logger):
    """When a non-Python file violation is dropped, logger.debug should be called."""
    violation = {"file_path": "src/data.json", "rule_id": "quality.no_dead_code"}
    filter_actionable_violations([violation])
    mock_logger.debug.assert_called_once()


@patch("will.workers.audit_violation_filter.logger")
# ID: 29733363-5d26-450b-864f-ef5a2f1bc720
def test_symbol_pair_logged_at_debug(mock_logger):
    """When symbol-pair violation is dropped, logger.debug should be called."""
    violation = {
        "file_path": "__symbol_pair__data.py",
        "rule_id": "quality.no_dead_code",
    }
    filter_actionable_violations([violation])
    mock_logger.debug.assert_called_once()


@patch("will.workers.audit_violation_filter.logger")
# ID: 7eae7280-09ec-4023-b3c3-3dc5e072f8f6
def test_malformed_rule_id_logged_at_debug(mock_logger):
    """When malformed rule_id violation is dropped, logger.debug should be called."""
    violation = {
        "file_path": "src/main.py",
        "rule_id": "enforcement/mappings/foo.yaml",
    }
    filter_actionable_violations([violation])
    mock_logger.debug.assert_called_once()


@patch("will.workers.audit_violation_filter.logger")
# ID: 7a093efb-ce7c-42ea-bb6a-a7358d0a3664
def test_no_logging_for_actionable_violation(mock_logger):
    """Actionable violations should not trigger any DEBUG logging."""
    violation = {"file_path": "src/main.py", "rule_id": "quality.no_dead_code"}
    filter_actionable_violations([violation])
    mock_logger.debug.assert_not_called()


# ID: 76c59b8a-558e-49f9-846b-c4c61ee63b4f
def test_uppercase_py_extension():
    """A .PY extension (uppercase) should not be considered Python source."""
    violation = {
        "file_path": "src/main.PY",
        "rule_id": "quality.no_dead_code",
    }
    result = filter_actionable_violations([violation])
    assert result == []


# ID: 066e6f37-89ce-4fbb-aab1-ee3e831957f2
def test_file_path_empty_string_not_dropped_by_sentinel():
    """Empty file_path should not match sentinel but should be dropped for not ending with .py."""
    violation = {"file_path": "", "rule_id": "quality.no_dead_code"}
    result = filter_actionable_violations([violation])
    assert result == []
