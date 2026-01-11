"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/cli_utils.py
- Symbol: CommandMetadata
- Status: 1 tests passed, some failed
- Passing tests: test_command_metadata_custom_initialization
- Generated: 2026-01-11 10:38:44
"""

from shared.cli_utils import CommandMetadata


def test_command_metadata_custom_initialization():
    """Test CommandMetadata with custom values."""
    metadata = CommandMetadata(dangerous=True, confirmation=True, requires_context=True)
    assert metadata.dangerous
    assert metadata.confirmation
    assert metadata.requires_context
