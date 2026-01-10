"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/component_primitive.py
- Symbol: ComponentPhase
- Status: 8 tests passed, some failed
- Passing tests: test_component_phase_values, test_component_phase_ordering, test_component_phase_string_behavior, test_component_phase_comparison, test_component_phase_membership, test_component_phase_iteration, test_component_phase_hashable, test_component_phase_docstring_presence
- Generated: 2026-01-11 00:14:24
"""

import pytest
from shared.component_primitive import ComponentPhase

def test_component_phase_values():
    """Test all phase values are correct strings."""
    assert ComponentPhase.INTERPRET == 'interpret'
    assert ComponentPhase.PARSE == 'parse'
    assert ComponentPhase.LOAD == 'load'
    assert ComponentPhase.AUDIT == 'audit'
    assert ComponentPhase.RUNTIME == 'runtime'
    assert ComponentPhase.EXECUTION == 'execution'

def test_component_phase_ordering():
    """Test that phases maintain their defined order."""
    phases = list(ComponentPhase)
    expected_order = [ComponentPhase.INTERPRET, ComponentPhase.PARSE, ComponentPhase.LOAD, ComponentPhase.AUDIT, ComponentPhase.RUNTIME, ComponentPhase.EXECUTION]
    assert phases == expected_order

def test_component_phase_string_behavior():
    """Test that ComponentPhase instances behave like strings."""
    phase = ComponentPhase.PARSE
    assert isinstance(phase, str)
    assert phase.upper() == 'PARSE'
    assert phase + '_phase' == 'parse_phase'
    assert len(phase) == 5

def test_component_phase_comparison():
    """Test comparisons between ComponentPhase instances and strings."""
    assert ComponentPhase.LOAD == 'load'
    assert ComponentPhase.LOAD != 'parse'
    assert 'load' == ComponentPhase.LOAD
    assert 'parse' != ComponentPhase.LOAD

def test_component_phase_membership():
    """Test membership checking."""
    assert 'interpret' in ComponentPhase
    assert 'runtime' in ComponentPhase
    assert 'invalid' not in ComponentPhase

def test_component_phase_iteration():
    """Test iteration over ComponentPhase."""
    phase_names = [phase.value for phase in ComponentPhase]
    assert phase_names == ['interpret', 'parse', 'load', 'audit', 'runtime', 'execution']

def test_component_phase_hashable():
    """Test that ComponentPhase instances are hashable (for use in dicts/sets)."""
    phase_dict = {ComponentPhase.INTERPRET: 'first', ComponentPhase.EXECUTION: 'last'}
    assert phase_dict[ComponentPhase.INTERPRET] == 'first'
    assert phase_dict[ComponentPhase.EXECUTION] == 'last'

def test_component_phase_docstring_presence():
    """Test that the class has appropriate documentation."""
    assert ComponentPhase.__doc__ is not None
    assert 'Constitutional phases' in ComponentPhase.__doc__
    assert 'INTERPRET' in ComponentPhase.__doc__
