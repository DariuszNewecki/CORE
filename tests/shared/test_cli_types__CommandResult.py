"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/cli_types.py
- Symbol: CommandResult
- Status: 14 tests passed, some failed
- Passing tests: test_command_result_initialization_with_required_fields, test_command_result_initialization_with_all_fields, test_command_result_post_init_validation_empty_name, test_command_result_post_init_validation_non_string_name, test_command_result_post_init_validation_non_dict_data, test_command_result_with_complex_data_structure, test_command_result_default_logs_is_empty_list, test_command_result_with_zero_duration, test_command_result_with_negative_duration, test_command_result_boolean_ok_values, test_command_result_with_empty_dict_data, test_command_result_name_with_dots, test_command_result_name_with_hyphens_and_underscores, test_command_result_multiple_instances_independence
- Generated: 2026-01-11 00:10:43
"""

import pytest
from shared.cli_types import CommandResult

def test_command_result_initialization_with_required_fields():
    """Test basic initialization with required fields"""
    result = CommandResult(name='test.command', ok=True, data={'count': 5})
    assert result.name == 'test.command'
    assert result.ok == True
    assert result.data == {'count': 5}
    assert result.duration_sec == 0.0
    assert result.logs == []

def test_command_result_initialization_with_all_fields():
    """Test initialization with all fields including optional ones"""
    logs = ['Starting operation', 'Operation completed']
    result = CommandResult(name='sync.data', ok=False, data={'synced': 3, 'failed': 1}, duration_sec=2.5, logs=logs)
    assert result.name == 'sync.data'
    assert result.ok == False
    assert result.data == {'synced': 3, 'failed': 1}
    assert result.duration_sec == 2.5
    assert result.logs == logs

def test_command_result_post_init_validation_empty_name():
    """Test validation rejects empty name"""
    with pytest.raises(ValueError, match='CommandResult.name must be non-empty string'):
        CommandResult(name='', ok=True, data={})

def test_command_result_post_init_validation_non_string_name():
    """Test validation rejects non-string name"""
    with pytest.raises(ValueError, match='CommandResult.name must be non-empty string'):
        CommandResult(name=123, ok=True, data={})

def test_command_result_post_init_validation_non_dict_data():
    """Test validation rejects non-dict data"""
    with pytest.raises(ValueError, match='CommandResult.data must be a dict'):
        CommandResult(name='test.command', ok=True, data='not a dict')

def test_command_result_with_complex_data_structure():
    """Test CommandResult can handle complex nested data structures"""
    complex_data = {'items': [{'id': 1, 'name': 'item1'}, {'id': 2, 'name': 'item2'}], 'metadata': {'total': 2, 'timestamp': '2024-01-01'}, 'nested': {'level1': {'level2': {'value': 'deep'}}}}
    result = CommandResult(name='complex.operation', ok=True, data=complex_data)
    assert result.name == 'complex.operation'
    assert result.ok == True
    assert result.data == complex_data
    assert result.data['items'][0]['name'] == 'item1'
    assert result.data['nested']['level1']['level2']['value'] == 'deep'

def test_command_result_default_logs_is_empty_list():
    """Test that default logs is an empty list, not None"""
    result = CommandResult(name='test.command', ok=True, data={})
    assert result.logs == []
    assert isinstance(result.logs, list)
    result.logs.append('new log')
    assert result.logs == ['new log']

def test_command_result_with_zero_duration():
    """Test duration_sec can be explicitly set to 0"""
    result = CommandResult(name='instant.command', ok=True, data={}, duration_sec=0.0)
    assert result.duration_sec == 0.0

def test_command_result_with_negative_duration():
    """Test duration_sec can be negative (edge case)"""
    result = CommandResult(name='weird.command', ok=True, data={}, duration_sec=-1.5)
    assert result.duration_sec == -1.5

def test_command_result_boolean_ok_values():
    """Test both boolean values for ok field"""
    result_true = CommandResult(name='success', ok=True, data={})
    result_false = CommandResult(name='failure', ok=False, data={})
    assert result_true.ok == True
    assert result_false.ok == False

def test_command_result_with_empty_dict_data():
    """Test CommandResult with empty data dict"""
    result = CommandResult(name='empty.data', ok=True, data={})
    assert result.data == {}
    assert isinstance(result.data, dict)
    assert len(result.data) == 0

def test_command_result_name_with_dots():
    """Test CommandResult name can contain dots (common pattern)"""
    result = CommandResult(name='module.submodule.command', ok=True, data={})
    assert result.name == 'module.submodule.command'

def test_command_result_name_with_hyphens_and_underscores():
    """Test CommandResult name with various characters"""
    result = CommandResult(name='fix-data_ids', ok=True, data={})
    assert result.name == 'fix-data_ids'

def test_command_result_multiple_instances_independence():
    """Test multiple CommandResult instances are independent"""
    result1 = CommandResult(name='first', ok=True, data={'value': 1}, duration_sec=1.0, logs=['log1'])
    result2 = CommandResult(name='second', ok=False, data={'value': 2}, duration_sec=2.0, logs=['log2'])
    assert result1.name == 'first'
    assert result2.name == 'second'
    assert result1.ok != result2.ok
    assert result1.data['value'] != result2.data['value']
    assert result1.duration_sec != result2.duration_sec
    assert result1.logs != result2.logs
