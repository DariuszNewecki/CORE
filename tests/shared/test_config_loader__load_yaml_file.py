"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/config_loader.py
- Symbol: load_yaml_file
- Status: 14 tests passed, some failed
- Passing tests: test_load_yaml_file_valid_yaml, test_load_yaml_file_valid_json, test_load_yaml_file_empty_yaml_returns_empty_dict, test_load_yaml_file_yaml_with_comments, test_load_yaml_file_yaml_with_only_comments, test_load_yaml_file_file_not_found, test_load_yaml_file_unsupported_extension, test_load_yaml_file_invalid_yaml_syntax, test_load_yaml_file_invalid_json_syntax, test_load_yaml_file_unicode_content, test_load_yaml_file_yaml_with_null_values, test_load_yaml_file_json_with_null_values, test_load_yaml_file_yaml_yml_extension_both_work, test_load_yaml_file_complex_nested_structure
- Generated: 2026-01-11 00:08:40
"""

import pytest
import json
import yaml
from pathlib import Path
from shared.config_loader import load_yaml_file

def test_load_yaml_file_valid_yaml(tmp_path):
    """Test loading a valid YAML file."""
    yaml_content = '\n    key1: value1\n    key2:\n      nested_key: nested_value\n    list_key:\n      - item1\n      - item2\n    '
    file_path = tmp_path / 'config.yaml'
    file_path.write_text(yaml_content, encoding='utf-8')
    result = load_yaml_file(file_path)
    expected = {'key1': 'value1', 'key2': {'nested_key': 'nested_value'}, 'list_key': ['item1', 'item2']}
    assert result == expected

def test_load_yaml_file_valid_json(tmp_path):
    """Test loading a valid JSON file."""
    json_content = '{"name": "test", "enabled": true, "count": 42}'
    file_path = tmp_path / 'config.json'
    file_path.write_text(json_content, encoding='utf-8')
    result = load_yaml_file(file_path)
    expected = {'name': 'test', 'enabled': True, 'count': 42}
    assert result == expected

def test_load_yaml_file_empty_yaml_returns_empty_dict(tmp_path):
    """Test loading an empty YAML file returns empty dict."""
    file_path = tmp_path / 'empty.yaml'
    file_path.write_text('', encoding='utf-8')
    result = load_yaml_file(file_path)
    assert result == {}

def test_load_yaml_file_yaml_with_comments(tmp_path):
    """Test loading YAML with comments."""
    yaml_content = '\n    # This is a comment\n    name: test\n    # Another comment\n    value: 100\n    '
    file_path = tmp_path / 'with_comments.yaml'
    file_path.write_text(yaml_content, encoding='utf-8')
    result = load_yaml_file(file_path)
    expected = {'name': 'test', 'value': 100}
    assert result == expected

def test_load_yaml_file_yaml_with_only_comments(tmp_path):
    """Test loading YAML with only comments returns empty dict."""
    yaml_content = '# Only comment\n# Another comment'
    file_path = tmp_path / 'only_comments.yaml'
    file_path.write_text(yaml_content, encoding='utf-8')
    result = load_yaml_file(file_path)
    assert result == {}

def test_load_yaml_file_file_not_found():
    """Test that FileNotFoundError is raised for non-existent file."""
    non_existent_path = Path('/non/existent/path/config.yaml')
    with pytest.raises(FileNotFoundError) as exc_info:
        load_yaml_file(non_existent_path)
    assert 'Config file not found' in str(exc_info.value)

def test_load_yaml_file_unsupported_extension(tmp_path):
    """Test that ValueError is raised for unsupported file types."""
    file_path = tmp_path / 'config.txt'
    file_path.write_text('some content', encoding='utf-8')
    with pytest.raises(ValueError) as exc_info:
        load_yaml_file(file_path)
    assert 'Unsupported config file type' in str(exc_info.value)

def test_load_yaml_file_invalid_yaml_syntax(tmp_path):
    """Test that ValueError is raised for invalid YAML syntax."""
    invalid_yaml = '\n    key: value\n      invalid_indentation: error\n    '
    file_path = tmp_path / 'invalid.yaml'
    file_path.write_text(invalid_yaml, encoding='utf-8')
    with pytest.raises(ValueError) as exc_info:
        load_yaml_file(file_path)
    assert 'Invalid config format' in str(exc_info.value)

def test_load_yaml_file_invalid_json_syntax(tmp_path):
    """Test that ValueError is raised for invalid JSON syntax."""
    invalid_json = '{"key": "value", missing_quotes: "error"}'
    file_path = tmp_path / 'invalid.json'
    file_path.write_text(invalid_json, encoding='utf-8')
    with pytest.raises(ValueError) as exc_info:
        load_yaml_file(file_path)
    assert 'Invalid config format' in str(exc_info.value)

def test_load_yaml_file_unicode_content(tmp_path):
    """Test loading file with Unicode characters."""
    yaml_content = '\n    name: "José"\n    description: "Special chars: © ® ™ …"\n    emoji: "🎉"\n    '
    file_path = tmp_path / 'unicode.yaml'
    file_path.write_text(yaml_content, encoding='utf-8')
    result = load_yaml_file(file_path)
    expected = {'name': 'José', 'description': 'Special chars: © ® ™ …', 'emoji': '🎉'}
    assert result == expected

def test_load_yaml_file_yaml_with_null_values(tmp_path):
    """Test loading YAML with null/None values."""
    yaml_content = '\n    key1: null\n    key2: ~\n    key3: value\n    '
    file_path = tmp_path / 'with_nulls.yaml'
    file_path.write_text(yaml_content, encoding='utf-8')
    result = load_yaml_file(file_path)
    expected = {'key1': None, 'key2': None, 'key3': 'value'}
    assert result == expected

def test_load_yaml_file_json_with_null_values(tmp_path):
    """Test loading JSON with null values."""
    json_content = '{"key1": null, "key2": "value"}'
    file_path = tmp_path / 'with_nulls.json'
    file_path.write_text(json_content, encoding='utf-8')
    result = load_yaml_file(file_path)
    expected = {'key1': None, 'key2': 'value'}
    assert result == expected

def test_load_yaml_file_yaml_yml_extension_both_work(tmp_path):
    """Test that both .yaml and .yml extensions work."""
    yaml_content = 'key: value'
    file_path1 = tmp_path / 'config.yaml'
    file_path1.write_text(yaml_content, encoding='utf-8')
    result1 = load_yaml_file(file_path1)
    file_path2 = tmp_path / 'config.yml'
    file_path2.write_text(yaml_content, encoding='utf-8')
    result2 = load_yaml_file(file_path2)
    expected = {'key': 'value'}
    assert result1 == expected
    assert result2 == expected

def test_load_yaml_file_complex_nested_structure(tmp_path):
    """Test loading complex nested YAML structure."""
    yaml_content = '\n    servers:\n      web:\n        host: "example.com"\n        ports: [80, 443]\n      db:\n        host: "localhost"\n        port: 5432\n    users:\n      - name: "Alice"\n        roles: ["admin", "user"]\n      - name: "Bob"\n        roles: ["user"]\n    '
    file_path = tmp_path / 'complex.yaml'
    file_path.write_text(yaml_content, encoding='utf-8')
    result = load_yaml_file(file_path)
    expected = {'servers': {'web': {'host': 'example.com', 'ports': [80, 443]}, 'db': {'host': 'localhost', 'port': 5432}}, 'users': [{'name': 'Alice', 'roles': ['admin', 'user']}, {'name': 'Bob', 'roles': ['user']}]}
    assert result == expected
