"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/context.py
- Symbol: CoreContext
- Status: 2 tests passed, some failed
- Passing tests: test_corecontext_with_registry, test_corecontext_repr_excludes_sensitive_fields
- Generated: 2026-01-11 01:15:00
"""

import pytest
from shared.context import CoreContext

def test_corecontext_with_registry():
    """Test CoreContext initialization with a registry."""
    test_registry = {'service': 'test'}
    context = CoreContext(registry=test_registry)
    assert context.registry == test_registry

def test_corecontext_repr_excludes_sensitive_fields():
    """Test that repr excludes fields marked with repr=False."""

    def factory():
        return 'service'
    context = CoreContext(registry='test_registry', context_service_factory=factory)
    repr_str = repr(context)
    assert 'registry' in repr_str or 'test_registry' in repr_str
    assert 'context_service_factory' not in repr_str
    assert 'factory' not in repr_str
    assert '_context_service' not in repr_str
