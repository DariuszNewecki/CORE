"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/cli_utils.py
- Symbol: CommandMetadata
- Status: 4 tests passed, some failed
- Passing tests: test_command_metadata_with_custom_values, test_command_metadata_mixed_values, test_command_metadata_type_annotations, test_command_metadata_repr
- Generated: 2026-01-11 00:47:28
"""

import pytest
from shared.cli_utils import CommandMetadata

def test_command_metadata_with_custom_values():
    """Test initialization with custom boolean values."""
    metadata = CommandMetadata(dangerous=True, confirmation=True, requires_context=True)
    assert metadata.dangerous == True
    assert metadata.confirmation == True
    assert metadata.requires_context == True

def test_command_metadata_mixed_values():
    """Test initialization with mixed boolean values."""
    metadata = CommandMetadata(dangerous=True, confirmation=False, requires_context=True)
    assert metadata.dangerous == True
    assert metadata.confirmation == False
    assert metadata.requires_context == True

def test_command_metadata_type_annotations():
    """Verify the class has the expected type annotations."""
    from typing import get_type_hints
    type_hints = get_type_hints(CommandMetadata)
    assert 'dangerous' in type_hints
    assert 'confirmation' in type_hints
    assert 'requires_context' in type_hints
    assert type_hints['dangerous'] == bool
    assert type_hints['confirmation'] == bool
    assert type_hints['requires_context'] == bool

def test_command_metadata_repr():
    """Test string representation of the class."""
    metadata = CommandMetadata(dangerous=True, confirmation=False, requires_context=True)
    repr_str = repr(metadata)
    assert 'CommandMetadata' in repr_str
    assert 'dangerous=True' in repr_str
    assert 'confirmation=False' in repr_str
    assert 'requires_context=True' in repr_str
