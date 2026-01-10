"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/cli_utils.py
- Symbol: CommandMetadata
- Status: 3 tests passed, some failed
- Passing tests: test_command_metadata_with_all_parameters, test_command_metadata_equality, test_command_metadata_combined_flags
- Generated: 2026-01-11 00:03:54
"""

import pytest
from shared.cli_utils import CommandMetadata

def test_command_metadata_with_all_parameters():
    """Test initialization with all parameters explicitly set."""
    metadata = CommandMetadata(dangerous=True, confirmation=True, requires_context=True)
    assert metadata.dangerous == True
    assert metadata.confirmation == True
    assert metadata.requires_context == True

def test_command_metadata_equality():
    """Test that two instances with same values are equal."""
    metadata1 = CommandMetadata(dangerous=True, confirmation=False, requires_context=True)
    metadata2 = CommandMetadata(dangerous=True, confirmation=False, requires_context=True)
    assert metadata1.dangerous == metadata2.dangerous
    assert metadata1.confirmation == metadata2.confirmation
    assert metadata1.requires_context == metadata2.requires_context

def test_command_metadata_combined_flags():
    """Test various combinations of boolean flags."""
    test_cases = [(True, False, False), (False, True, False), (False, False, True), (True, True, False), (True, False, True), (False, True, True), (True, True, True)]
    for dangerous, confirmation, requires_context in test_cases:
        metadata = CommandMetadata(dangerous=dangerous, confirmation=confirmation, requires_context=requires_context)
        assert metadata.dangerous == dangerous
        assert metadata.confirmation == confirmation
        assert metadata.requires_context == requires_context
