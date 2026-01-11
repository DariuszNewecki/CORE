"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/evaluators/failure_evaluator.py
- Symbol: FailureEvaluator
- Status: 18 tests passed, some failed
- Passing tests: test_extract_pattern_invalid_import, test_extract_pattern_nameerror, test_extract_pattern_type_introspection, test_extract_pattern_attributeerror_mocks, test_extract_pattern_assertionerror, test_extract_pattern_sqlalchemy, test_extract_pattern_runtime_constraints, test_extract_pattern_unknown, test_execute_first_occurrence, test_execute_second_occurrence, test_execute_third_occurrence, test_execute_multiple_patterns, test_execute_empty_pattern_history, test_get_pattern_summary_empty, test_get_pattern_summary_single_pattern, test_get_pattern_summary_multiple_patterns, test_execute_result_structure, test_case_insensitive_pattern_matching
- Generated: 2026-01-11 03:26:00
"""

import pytest
from body.evaluators.failure_evaluator import FailureEvaluator
from collections import Counter

@pytest.mark.asyncio
async def test_extract_pattern_invalid_import():
    """Test ModuleNotFoundError and ImportError patterns."""
    evaluator = FailureEvaluator()
    error1 = "ModuleNotFoundError: No module named 'nonexistent_module'"
    assert evaluator._extract_pattern(error1) == 'invalid_import'
    error2 = "ImportError: cannot import name 'MissingClass' from 'some.module'"
    assert evaluator._extract_pattern(error2) == 'invalid_import'
    error3 = "MODULENOTFOUNDERROR: No module named 'test'"
    assert evaluator._extract_pattern(error3) == 'invalid_import'

@pytest.mark.asyncio
async def test_extract_pattern_nameerror():
    """Test NameError pattern detection."""
    evaluator = FailureEvaluator()
    error = "NameError: name 'undefined_variable' is not defined"
    assert evaluator._extract_pattern(error) == 'logic_error_missing_name'
    error2 = "NAMEERROR: 'x' is not defined"
    assert evaluator._extract_pattern(error2) == 'logic_error_missing_name'

@pytest.mark.asyncio
async def test_extract_pattern_type_introspection():
    """Test type introspection patterns with isinstance and ClassVar/Mapped."""
    evaluator = FailureEvaluator()
    error1 = 'TypeError: isinstance() arg 2 must be a type or tuple of types, got ClassVar'
    assert evaluator._extract_pattern(error1) == 'type_introspection'
    error2 = 'Error in isinstance check with Mapped column'
    assert evaluator._extract_pattern(error2) == 'type_introspection'
    error3 = 'isinstance() and typing module conflict'
    assert evaluator._extract_pattern(error3) == 'type_introspection'
    error4 = 'isinstance() argument must be a type'
    assert evaluator._extract_pattern(error4) != 'type_introspection'

@pytest.mark.asyncio
async def test_extract_pattern_attributeerror_mocks():
    """Test AttributeError patterns related to mocking."""
    evaluator = FailureEvaluator()
    error1 = "AttributeError: 'MagicMock' object has no attribute 'missing_method'"
    assert evaluator._extract_pattern(error1) == 'mock_placement'
    error2 = 'AttributeError: patched object missing attribute'
    assert evaluator._extract_pattern(error2) == 'mock_placement'
    error3 = "AttributeError: module 'datetime' has no attribute 'now'"
    assert evaluator._extract_pattern(error3) == 'mock_datetime'
    error4 = "AttributeError: 'NoneType' object has no attribute 'something'"
    assert evaluator._extract_pattern(error4) == 'attribute_error_generic'

@pytest.mark.asyncio
async def test_extract_pattern_assertionerror():
    """Test AssertionError pattern classification."""
    evaluator = FailureEvaluator()
    error1 = 'AssertionError: 1 == 2'
    assert evaluator._extract_pattern(error1) == 'assertion_comparison'
    error2 = 'AssertionError: <object at 0x7f8a1b2c3d90> == <object at 0x7f8a1b2c3e10>'
    assert evaluator._extract_pattern(error2) == 'object_identity_comparison'
    error3 = 'AssertionError: Something went wrong'
    assert evaluator._extract_pattern(error3) == 'assertion_error'

@pytest.mark.asyncio
async def test_extract_pattern_sqlalchemy():
    """Test SQLAlchemy related patterns."""
    evaluator = FailureEvaluator()
    error1 = 'sqlalchemy.orm.exc.DetachedInstanceError: Session issues'
    assert evaluator._extract_pattern(error1) == 'sqlalchemy_session'
    error2 = 'sqlalchemy.exc.InvalidRequestError: relationship loading'
    assert evaluator._extract_pattern(error2) == 'sqlalchemy_relationship'
    error3 = 'sqlalchemy.exc.OperationalError: database connection failed'
    assert evaluator._extract_pattern(error3) == 'sqlalchemy_generic'

@pytest.mark.asyncio
async def test_extract_pattern_runtime_constraints():
    """Test timeout and fixture patterns."""
    evaluator = FailureEvaluator()
    error1 = 'TimeoutError: Test timed out after 30 seconds'
    assert evaluator._extract_pattern(error1) == 'test_timeout'
    error2 = 'The test timed out while waiting for response'
    assert evaluator._extract_pattern(error2) == 'test_timeout'
    error3 = "FixtureNotFoundError: The fixture 'db' was not found"
    assert evaluator._extract_pattern(error3) == 'fixture_error'
    error4 = "Fixture 'setup' error occurred during execution"
    assert evaluator._extract_pattern(error4) == 'fixture_error'

@pytest.mark.asyncio
async def test_extract_pattern_unknown():
    """Test fallback to unknown pattern."""
    evaluator = FailureEvaluator()
    error = 'Some random error message without known keywords'
    assert evaluator._extract_pattern(error) == 'unknown'
    assert evaluator._extract_pattern('') == 'unknown'

@pytest.mark.asyncio
async def test_execute_first_occurrence():
    """Test execute with first occurrence of a pattern."""
    evaluator = FailureEvaluator()
    error = 'NameError: test error'
    result = await evaluator.execute(error=error, pattern_history=None)
    assert result.data['pattern'] == 'logic_error_missing_name'
    assert result.data['occurrences'] == 1
    assert result.data['should_switch'] == False
    assert result.data['recommendation'] == 'retry'
    assert result.confidence == 0.5
    assert result.next_suggested == 'test_generator'

@pytest.mark.asyncio
async def test_execute_second_occurrence():
    """Test execute with second occurrence of same pattern."""
    evaluator = FailureEvaluator()
    error = 'NameError: test error'
    pattern_history = ['logic_error_missing_name']
    result = await evaluator.execute(error=error, pattern_history=pattern_history)
    assert result.data['pattern'] == 'logic_error_missing_name'
    assert result.data['occurrences'] == 2
    assert result.data['should_switch'] == False
    assert result.data['recommendation'] == 'adjust_prompt'
    assert result.confidence == 0.7
    assert result.next_suggested == 'test_generator'

@pytest.mark.asyncio
async def test_execute_third_occurrence():
    """Test execute with third occurrence triggers strategy switch."""
    evaluator = FailureEvaluator()
    error = 'NameError: test error'
    pattern_history = ['logic_error_missing_name', 'logic_error_missing_name']
    result = await evaluator.execute(error=error, pattern_history=pattern_history)
    assert result.data['pattern'] == 'logic_error_missing_name'
    assert result.data['occurrences'] == 3
    assert result.data['should_switch'] == True
    assert result.data['recommendation'] == 'switch_strategy'
    assert result.confidence == 0.95
    assert result.next_suggested == 'test_strategist'

@pytest.mark.asyncio
async def test_execute_multiple_patterns():
    """Test execute with mixed pattern history."""
    evaluator = FailureEvaluator()
    error = 'AssertionError: test'
    pattern_history = ['invalid_import', 'logic_error_missing_name', 'invalid_import']
    result = await evaluator.execute(error=error, pattern_history=pattern_history)
    assert result.data['pattern'] == 'assertion_error'
    assert result.data['occurrences'] == 1
    assert result.data['should_switch'] == False
    assert result.data['recommendation'] == 'retry'

@pytest.mark.asyncio
async def test_execute_empty_pattern_history():
    """Test execute with empty pattern history list."""
    evaluator = FailureEvaluator()
    error = 'ModuleNotFoundError: test'
    result = await evaluator.execute(error=error, pattern_history=[])
    assert result.data['pattern'] == 'invalid_import'
    assert result.data['occurrences'] == 1
    assert result.metadata['pattern_history'] == ['invalid_import']

@pytest.mark.asyncio
async def test_get_pattern_summary_empty():
    """Test pattern summary with empty history."""
    evaluator = FailureEvaluator()
    summary = evaluator.get_pattern_summary([])
    assert summary['total'] == 0
    assert summary['unique'] == 0
    assert summary['most_common'] is None
    assert summary['patterns'] == {}

@pytest.mark.asyncio
async def test_get_pattern_summary_single_pattern():
    """Test pattern summary with single pattern repeated."""
    evaluator = FailureEvaluator()
    history = ['invalid_import', 'invalid_import', 'invalid_import']
    summary = evaluator.get_pattern_summary(history)
    assert summary['total'] == 3
    assert summary['unique'] == 1
    assert summary['most_common'] == 'invalid_import'
    assert summary['patterns'] == {'invalid_import': 3}

@pytest.mark.asyncio
async def test_get_pattern_summary_multiple_patterns():
    """Test pattern summary with multiple distinct patterns."""
    evaluator = FailureEvaluator()
    history = ['invalid_import', 'logic_error_missing_name', 'invalid_import', 'assertion_error']
    summary = evaluator.get_pattern_summary(history)
    assert summary['total'] == 4
    assert summary['unique'] == 3
    assert summary['most_common'] == 'invalid_import'
    assert summary['patterns'] == {'invalid_import': 2, 'logic_error_missing_name': 1, 'assertion_error': 1}

@pytest.mark.asyncio
async def test_execute_result_structure():
    """Verify complete ComponentResult structure."""
    evaluator = FailureEvaluator()
    error = 'AttributeError: mock issue'
    result = await evaluator.execute(error=error, pattern_history=None)
    assert result.ok == True
    assert result.component_id == evaluator.component_id
    assert result.phase == evaluator.phase
    assert isinstance(result.duration_sec, float)
    assert result.duration_sec > 0
    assert 'pattern_history' in result.metadata
    assert 'summary' in result.metadata
    assert isinstance(result.metadata['summary'], dict)
    summary = result.metadata['summary']
    assert 'total' in summary
    assert 'unique' in summary
    assert 'most_common' in summary
    assert 'patterns' in summary

@pytest.mark.asyncio
async def test_case_insensitive_pattern_matching():
    """Test that pattern matching is case insensitive."""
    evaluator = FailureEvaluator()
    error1 = 'MODULENotFoundError: Test'
    error2 = 'assertionERROR: Failed'
    error3 = 'SQLALCHEMY: Database issue'
    assert evaluator._extract_pattern(error1) == 'invalid_import'
    assert evaluator._extract_pattern(error2) == 'assertion_error'
    assert evaluator._extract_pattern(error3) == 'sqlalchemy_generic'
