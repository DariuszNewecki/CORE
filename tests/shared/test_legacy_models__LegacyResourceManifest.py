"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/legacy_models.py
- Symbol: LegacyResourceManifest
- Status: 3 tests passed, some failed
- Passing tests: test_empty_initialization, test_type_validation, test_immutability_of_list_reference
- Generated: 2026-01-11 01:05:12
"""

import pytest
from shared.legacy_models import LegacyResourceManifest

class TestLegacyResourceManifest:

    def test_empty_initialization(self):
        """Test that LegacyResourceManifest can be initialized with empty list."""
        manifest = LegacyResourceManifest(llm_resources=[])
        assert manifest.llm_resources == []
        assert isinstance(manifest.llm_resources, list)

    def test_type_validation(self):
        """Test that LegacyResourceManifest validates llm_resources type."""
        with pytest.raises(ValueError):
            LegacyResourceManifest(llm_resources='not a list')
        with pytest.raises(ValueError):
            LegacyResourceManifest(llm_resources={'key': 'value'})

    def test_immutability_of_list_reference(self):
        """Test that modifying the original list doesn't affect the model."""
        original_list = []
        manifest = LegacyResourceManifest(llm_resources=original_list)
        original_list.append('new item')
        assert manifest.llm_resources == []
