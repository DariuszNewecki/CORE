"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/legacy_models.py
- Symbol: LegacyCliRegistry
- Status: 2 tests passed, some failed
- Passing tests: test_legacy_cli_registry_empty_commands, test_legacy_cli_registry_field_validation
- Generated: 2026-01-11 01:04:24
"""

import pytest
from shared.legacy_models import LegacyCliRegistry, LegacyCliCommand

def test_legacy_cli_registry_empty_commands():
    """Test that a LegacyCliRegistry can be initialized with an empty command list."""
    registry = LegacyCliRegistry(commands=[])
    assert registry.commands == []
    assert isinstance(registry.commands, list)

def test_legacy_cli_registry_field_validation():
    """Test that Pydantic validates the 'commands' field type."""
    with pytest.raises(ValueError):
        LegacyCliRegistry(commands='not a list')
    with pytest.raises(ValueError):
        LegacyCliRegistry(commands=[{'invalid': 'object'}])
