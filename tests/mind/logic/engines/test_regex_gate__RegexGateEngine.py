"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/logic/engines/regex_gate.py
- Symbol: RegexGateEngine
- Status: 14 tests passed, some failed
- Passing tests: test_regex_gate_engine_initialization, test_verify_naming_pattern_success, test_verify_naming_pattern_failure, test_verify_forbidden_patterns_string_param, test_verify_forbidden_patterns_list_param, test_verify_forbidden_patterns_multiline, test_verify_required_patterns_success, test_verify_required_patterns_failure, test_verify_required_patterns_string_param, test_verify_all_parameters_combined, test_verify_file_not_found, test_verify_empty_file, test_verify_no_violations, test_verify_patterns_alias
- Generated: 2026-01-11 02:23:54
"""

import pytest
import asyncio
from pathlib import Path
from mind.logic.engines.regex_gate import RegexGateEngine

@pytest.mark.asyncio
async def test_regex_gate_engine_initialization():
    """Test that RegexGateEngine initializes correctly."""
    engine = RegexGateEngine()
    assert engine.engine_id == 'regex_gate'

@pytest.mark.asyncio
async def test_verify_naming_pattern_success(tmp_path):
    """Test filename pattern matching when pattern matches."""
    engine = RegexGateEngine()
    file_path = tmp_path / 'test_file.py'
    file_path.write_text('content', encoding='utf-8')
    params = {'naming_pattern': 'test_.*\\.py'}
    result = await engine.verify(file_path, params)
    assert result.ok == True
    assert result.message == 'Pattern compliance verified.'
    assert result.violations == []
    assert result.engine_id == 'regex_gate'

@pytest.mark.asyncio
async def test_verify_naming_pattern_failure(tmp_path):
    """Test filename pattern matching when pattern doesn't match."""
    engine = RegexGateEngine()
    file_path = tmp_path / 'wrong_name.txt'
    file_path.write_text('content', encoding='utf-8')
    params = {'naming_pattern': '^test_.*\\.py$'}
    result = await engine.verify(file_path, params)
    assert result.ok == False
    assert 'Constitutional Violation' in result.message
    assert len(result.violations) == 1
    assert 'Naming Violation' in result.violations[0]
    assert result.engine_id == 'regex_gate'

@pytest.mark.asyncio
async def test_verify_forbidden_patterns_string_param(tmp_path):
    """Test forbidden patterns with string parameter (should be converted to list)."""
    engine = RegexGateEngine()
    file_path = tmp_path / 'test.txt'
    file_path.write_text('This contains SECRET_KEY=abc123', encoding='utf-8')
    params = {'forbidden_patterns': 'SECRET_KEY=.*'}
    result = await engine.verify(file_path, params)
    assert result.ok == False
    assert len(result.violations) == 1
    assert 'Forbidden Content' in result.violations[0]
    assert 'Line 1' in result.violations[0]

@pytest.mark.asyncio
async def test_verify_forbidden_patterns_list_param(tmp_path):
    """Test forbidden patterns with list parameter."""
    engine = RegexGateEngine()
    file_path = tmp_path / 'test.txt'
    file_path.write_text('First line\nSECRET=abc\nThird line\nPASSWORD=123', encoding='utf-8')
    params = {'forbidden_patterns': ['SECRET=.*', 'PASSWORD=.*']}
    result = await engine.verify(file_path, params)
    assert result.ok == False
    assert len(result.violations) == 2
    assert any(('Line 2' in v for v in result.violations))
    assert any(('Line 4' in v for v in result.violations))

@pytest.mark.asyncio
async def test_verify_forbidden_patterns_multiline(tmp_path):
    """Test forbidden patterns with multiline content."""
    engine = RegexGateEngine()
    file_path = tmp_path / 'test.txt'
    content = 'Line 1\nLine 2\nSecret: abc123\nLine 4\nLine 5'
    file_path.write_text(content, encoding='utf-8')
    params = {'forbidden_patterns': ['Secret: .*']}
    result = await engine.verify(file_path, params)
    assert result.ok == False
    assert len(result.violations) == 1
    assert 'Line 3' in result.violations[0]

@pytest.mark.asyncio
async def test_verify_required_patterns_success(tmp_path):
    """Test required patterns that are present in content."""
    engine = RegexGateEngine()
    file_path = tmp_path / 'test.py'
    content = '#!/usr/bin/env python3\n# Copyright 2024\n# License: MIT\n\ndef main():\n    pass\n'
    file_path.write_text(content, encoding='utf-8')
    params = {'required_patterns': ['^#!/usr/bin/env python3', '^# Copyright']}
    result = await engine.verify(file_path, params)
    assert result.ok == True
    assert result.message == 'Pattern compliance verified.'
    assert result.violations == []

@pytest.mark.asyncio
async def test_verify_required_patterns_failure(tmp_path):
    """Test required patterns that are missing from content."""
    engine = RegexGateEngine()
    file_path = tmp_path / 'test.py'
    content = 'def main():\n    pass\n'
    file_path.write_text(content, encoding='utf-8')
    params = {'required_patterns': ['^#!/usr/bin/env python3', '^# Copyright']}
    result = await engine.verify(file_path, params)
    assert result.ok == False
    assert len(result.violations) == 2
    assert all(('Missing Required Content' in v for v in result.violations))

@pytest.mark.asyncio
async def test_verify_required_patterns_string_param(tmp_path):
    """Test required patterns with string parameter (should be converted to list)."""
    engine = RegexGateEngine()
    file_path = tmp_path / 'test.py'
    content = 'Copyright notice here'
    file_path.write_text(content, encoding='utf-8')
    params = {'required_patterns': 'Copyright'}
    result = await engine.verify(file_path, params)
    assert result.ok == True
    assert result.violations == []

@pytest.mark.asyncio
async def test_verify_all_parameters_combined(tmp_path):
    """Test with all parameter types combined."""
    engine = RegexGateEngine()
    file_path = tmp_path / 'test_module.py'
    content = '#!/usr/bin/env python3\n# Copyright 2024\nAPI_KEY = "should_not_be_here"\ndef main():\n    pass\n'
    file_path.write_text(content, encoding='utf-8')
    params = {'naming_pattern': '.*\\.py$', 'forbidden_patterns': ['API_KEY\\s*=\\s*".*"'], 'required_patterns': ['^#!/usr/bin/env python3', '^# Copyright']}
    result = await engine.verify(file_path, params)
    assert result.ok == False
    assert len(result.violations) == 1
    assert 'Forbidden Content' in result.violations[0]
    assert 'Line 3' in result.violations[0]

@pytest.mark.asyncio
async def test_verify_file_not_found(tmp_path):
    """Test behavior when file doesn't exist."""
    engine = RegexGateEngine()
    file_path = tmp_path / 'nonexistent.txt'
    params = {}
    result = await engine.verify(file_path, params)
    assert result.ok == False
    assert 'IO Error' in result.message
    assert result.violations == []
    assert result.engine_id == 'regex_gate'

@pytest.mark.asyncio
async def test_verify_empty_file(tmp_path):
    """Test with an empty file."""
    engine = RegexGateEngine()
    file_path = tmp_path / 'empty.txt'
    file_path.write_text('', encoding='utf-8')
    params = {'forbidden_patterns': ['secret'], 'required_patterns': ['header']}
    result = await engine.verify(file_path, params)
    assert result.ok == False
    assert len(result.violations) == 1
    assert 'Missing Required Content' in result.violations[0]

@pytest.mark.asyncio
async def test_verify_no_violations(tmp_path):
    """Test when no violations are found."""
    engine = RegexGateEngine()
    file_path = tmp_path / 'valid.py'
    content = 'Valid content here'
    file_path.write_text(content, encoding='utf-8')
    params = {'naming_pattern': '.*\\.py$', 'forbidden_patterns': [], 'required_patterns': []}
    result = await engine.verify(file_path, params)
    assert result.ok == True
    assert result.message == 'Pattern compliance verified.'
    assert result.violations == []
    assert result.engine_id == 'regex_gate'

@pytest.mark.asyncio
async def test_verify_patterns_alias(tmp_path):
    """Test that 'patterns' alias works for forbidden_patterns."""
    engine = RegexGateEngine()
    file_path = tmp_path / 'test.txt'
    file_path.write_text('Contains secret data', encoding='utf-8')
    params = {'patterns': 'secret'}
    result = await engine.verify(file_path, params)
    assert result.ok == False
    assert len(result.violations) == 1
    assert 'Forbidden Content' in result.violations[0]
