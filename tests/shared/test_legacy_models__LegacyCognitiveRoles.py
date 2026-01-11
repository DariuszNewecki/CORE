"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/legacy_models.py
- Symbol: LegacyCognitiveRoles
- Status: 2 tests passed, some failed
- Passing tests: test_legacy_cognitive_roles_initialization, test_legacy_cognitive_roles_field_type_validation
- Generated: 2026-01-11 01:06:14
"""

import pytest
from shared.legacy_models import LegacyCognitiveRoles

def test_legacy_cognitive_roles_initialization():
    """Test that the model can be initialized with an empty list."""
    model = LegacyCognitiveRoles(cognitive_roles=[])
    assert model.cognitive_roles == []

def test_legacy_cognitive_roles_field_type_validation():
    """Test that the model enforces the type of the cognitive_roles field."""
    with pytest.raises(Exception):
        LegacyCognitiveRoles(cognitive_roles='not a list')
