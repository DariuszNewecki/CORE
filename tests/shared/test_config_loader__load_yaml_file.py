"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/config_loader.py
- Symbol: load_yaml_file
- Status: 13 tests passed, some failed
- Passing tests: test_load_yaml_file_valid_yaml, test_load_yaml_file_valid_yml_extension, test_load_yaml_file_valid_json, test_load_yaml_file_empty_yaml_returns_empty_dict, test_load_yaml_file_yaml_with_only_comments, test_load_yaml_file_file_not_found, test_load_yaml_file_unsupported_extension, test_load_yaml_file_invalid_yaml_syntax, test_load_yaml_file_invalid_json_syntax, test_load_yaml_file_unicode_decode_error, test_load_yaml_file_complex_yaml_structure, test_load_yaml_file_json_with_null_values, test_load_yaml_file_yaml_with_anchors_and_aliases
- Generated: 2026-01-11 00:52:34
"""

import pytest
from pathlib import Path
from shared.config_loader import load_yaml_file
import json
import yaml

def test_load_yaml_file_valid_yaml(tmp_path):
    """Test loading a valid YAML file."""
    yaml_content = '\ndatabase:\n  host: localhost\n  port: 5432\n  name: test_db\n'
    file_path = tmp_path / 'config.yaml'
    file_path.write_text(yaml_content, encoding='utf-8')
    result = load_yaml_file(file_path)
    expected = {'database': {'host': 'localhost', 'port': 5432, 'name': 'test_db'}}
    assert result == expected

def test_load_yaml_file_valid_yml_extension(tmp_path):
    """Test loading a valid YAML file with .yml extension."""
    yaml_content = 'key: value'
    file_path = tmp_path / 'config.yml'
    file_path.write_text(yaml_content, encoding='utf-8')
    result = load_yaml_file(file_path)
    assert result == {'key': 'value'}

def test_load_yaml_file_valid_json(tmp_path):
    """Test loading a valid JSON file."""
    json_content = '{"app": {"name": "test", "version": "1.0.0"}}'
    file_path = tmp_path / 'config.json'
    file_path.write_text(json_content, encoding='utf-8')
    result = load_yaml_file(file_path)
    assert result == {'app': {'name': 'test', 'version': '1.0.0'}}

def test_load_yaml_file_empty_yaml_returns_empty_dict(tmp_path):
    """Test loading an empty YAML file returns empty dict."""
    file_path = tmp_path / 'empty.yaml'
    file_path.write_text('', encoding='utf-8')
    result = load_yaml_file(file_path)
    assert result == {}

def test_load_yaml_file_yaml_with_only_comments(tmp_path):
    """Test YAML file with only comments returns empty dict."""
    yaml_content = '# This is a comment\n# Another comment'
    file_path = tmp_path / 'comments.yaml'
    file_path.write_text(yaml_content, encoding='utf-8')
    result = load_yaml_file(file_path)
    assert result == {}

def test_load_yaml_file_file_not_found():
    """Test FileNotFoundError when file doesn't exist."""
    non_existent_path = Path('/non/existent/path/config.yaml')
    with pytest.raises(FileNotFoundError) as exc_info:
        load_yaml_file(non_existent_path)
    assert 'Config file not found' in str(exc_info.value)

def test_load_yaml_file_unsupported_extension(tmp_path):
    """Test ValueError for unsupported file extension."""
    file_path = tmp_path / 'config.txt'
    file_path.write_text('some content', encoding='utf-8')
    with pytest.raises(ValueError) as exc_info:
        load_yaml_file(file_path)
    assert 'Unsupported config file type' in str(exc_info.value)

def test_load_yaml_file_invalid_yaml_syntax(tmp_path):
    """Test ValueError for invalid YAML syntax."""
    invalid_yaml = 'key: [unclosed list'
    file_path = tmp_path / 'invalid.yaml'
    file_path.write_text(invalid_yaml, encoding='utf-8')
    with pytest.raises(ValueError) as exc_info:
        load_yaml_file(file_path)
    assert 'Invalid config format' in str(exc_info.value)

def test_load_yaml_file_invalid_json_syntax(tmp_path):
    """Test ValueError for invalid JSON syntax."""
    invalid_json = '{"key": "value"'
    file_path = tmp_path / 'invalid.json'
    file_path.write_text(invalid_json, encoding='utf-8')
    with pytest.raises(ValueError) as exc_info:
        load_yaml_file(file_path)
    assert 'Invalid config format' in str(exc_info.value)

def test_load_yaml_file_unicode_decode_error(tmp_path):
    """Test ValueError for encoding issues."""
    file_path = tmp_path / 'bad_encoding.yaml'
    file_path.write_bytes(b'\xff\xfe')
    with pytest.raises(ValueError) as exc_info:
        load_yaml_file(file_path)
    assert 'Encoding error' in str(exc_info.value)

def test_load_yaml_file_complex_yaml_structure(tmp_path):
    """Test loading YAML with complex nested structure."""
    yaml_content = '\nservices:\n  - name: api\n    ports:\n      - 8080\n      - 8443\n    enabled: true\n  - name: database\n    replicas: 3\n    config:\n      max_connections: 100\n      timeout: 30s\n'
    file_path = tmp_path / 'complex.yaml'
    file_path.write_text(yaml_content, encoding='utf-8')
    result = load_yaml_file(file_path)
    expected = {'services': [{'name': 'api', 'ports': [8080, 8443], 'enabled': True}, {'name': 'database', 'replicas': 3, 'config': {'max_connections': 100, 'timeout': '30s'}}]}
    assert result == expected

def test_load_yaml_file_json_with_null_values(tmp_path):
    """Test loading JSON with null values."""
    json_content = '{"name": "test", "optional": null, "count": 42}'
    file_path = tmp_path / 'with_null.json'
    file_path.write_text(json_content, encoding='utf-8')
    result = load_yaml_file(file_path)
    assert result == {'name': 'test', 'optional': None, 'count': 42}

def test_load_yaml_file_yaml_with_anchors_and_aliases(tmp_path):
    """Test loading YAML with anchors and aliases."""
    yaml_content = '\ndefaults: &defaults\n  timeout: 30\n  retries: 3\n\nservice:\n  <<: *defaults\n  name: api\n'
    file_path = tmp_path / 'anchors.yaml'
    file_path.write_text(yaml_content, encoding='utf-8')
    result = load_yaml_file(file_path)
    expected = {'defaults': {'timeout': 30, 'retries': 3}, 'service': {'timeout': 30, 'retries': 3, 'name': 'api'}}
    assert result == expected
