"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/policy_gate.py
- Symbol: ActionStep
- Status: 5 tests passed, some failed
- Passing tests: test_actionstep_creation_with_minimal_fields, test_actionstep_metadata_is_mapping, test_actionstep_target_path_can_be_any_string, test_actionstep_name_is_required_string, test_actionstep_equality_and_representation
- Generated: 2026-01-11 02:02:00
"""

import pytest
from mind.governance.policy_gate import ActionStep

def test_actionstep_creation_with_minimal_fields():
    """Test basic instantiation with required fields."""
    step = ActionStep(name='file.format.black', target_path=None, metadata={})
    assert step.name == 'file.format.black'
    assert step.target_path is None
    assert step.metadata == {}

def test_actionstep_metadata_is_mapping():
    """Test that metadata can be any Mapping."""
    from collections.abc import Mapping
    metadata = {'key': 'value', 'list': [1, 2, 3]}
    step = ActionStep(name='test.step', target_path=None, metadata=metadata)
    assert isinstance(step.metadata, Mapping)
    assert step.metadata['key'] == 'value'
    assert step.metadata['list'] == [1, 2, 3]

def test_actionstep_target_path_can_be_any_string():
    """Test target_path with various string values."""
    step1 = ActionStep(name='a', target_path='', metadata={})
    assert step1.target_path == ''
    step2 = ActionStep(name='b', target_path='folder/file.txt', metadata={})
    assert step2.target_path == 'folder/file.txt'
    step3 = ActionStep(name='c', target_path='/absolute/path', metadata={})
    assert step3.target_path == '/absolute/path'

def test_actionstep_name_is_required_string():
    """Test that name must be a string (enforced by type hints/runtime)."""
    step = ActionStep(name='required.name', target_path=None, metadata={})
    assert isinstance(step.name, str)
    assert step.name == 'required.name'

def test_actionstep_equality_and_representation():
    """Test basic __eq__ and __repr__ behavior (if defined by dataclass)."""
    step1 = ActionStep(name='x', target_path='a', metadata={'k': 1})
    step2 = ActionStep(name='x', target_path='a', metadata={'k': 1})
    assert step1.name == step2.name
    assert step1.target_path == step2.target_path
    assert step1.metadata == step2.metadata
    assert 'ActionStep' in repr(step1)
