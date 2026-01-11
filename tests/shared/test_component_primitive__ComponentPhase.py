"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/component_primitive.py
- Symbol: ComponentPhase
- Status: verified_in_sandbox
- Generated: 2026-01-11 00:58:14
"""

import pytest
from shared.component_primitive import ComponentPhase

# Detected return type: ComponentPhase is an Enum member (string subclass).

def test_component_phase_is_enum():
    """Test that ComponentPhase is an Enum with string values."""
    assert isinstance(ComponentPhase.INTERPRET, ComponentPhase)
    assert isinstance(ComponentPhase.PARSE, ComponentPhase)
    assert isinstance(ComponentPhase.LOAD, ComponentPhase)
    assert isinstance(ComponentPhase.AUDIT, ComponentPhase)
    assert isinstance(ComponentPhase.RUNTIME, ComponentPhase)
    assert isinstance(ComponentPhase.EXECUTION, ComponentPhase)

def test_component_phase_values():
    """Test the specific string values of each phase."""
    assert ComponentPhase.INTERPRET == "interpret"
    assert ComponentPhase.PARSE == "parse"
    assert ComponentPhase.LOAD == "load"
    assert ComponentPhase.AUDIT == "audit"
    assert ComponentPhase.RUNTIME == "runtime"
    assert ComponentPhase.EXECUTION == "execution"

def test_component_phase_string_behavior():
    """Test that ComponentPhase members behave like strings."""
    phase = ComponentPhase.PARSE
    # String concatenation
    assert phase + ".ext" == "parse.ext"
    # String methods
    assert phase.upper() == "PARSE"
    assert phase.capitalize() == "Parse"
    # Membership check
    assert isinstance(phase, str)

def test_component_phase_iteration_and_membership():
    """Test that all expected members exist and can be iterated."""
    expected_phases = {"interpret", "parse", "load", "audit", "runtime", "execution"}
    actual_phases = {member.value for member in ComponentPhase}
    assert actual_phases == expected_phases
    assert len(list(ComponentPhase)) == 6

def test_component_phase_ordering():
    """Test that the order of members matches the documented execution order."""
    phases_in_order = list(ComponentPhase)
    assert phases_in_order[0] == ComponentPhase.INTERPRET
    assert phases_in_order[1] == ComponentPhase.PARSE
    assert phases_in_order[2] == ComponentPhase.LOAD
    assert phases_in_order[3] == ComponentPhase.AUDIT
    assert phases_in_order[4] == ComponentPhase.RUNTIME
    assert phases_in_order[5] == ComponentPhase.EXECUTION
