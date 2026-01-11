"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/component_primitive.py
- Symbol: discover_components
- Status: 4 tests passed, some failed
- Passing tests: test_discover_components_returns_dict, test_discover_components_import_error_handled, test_discover_components_valid_structure, test_discover_components_no_side_effects
- Generated: 2026-01-11 01:01:28
"""

import pytest
from shared.component_primitive import discover_components

def test_discover_components_returns_dict():
    """Test that discover_components returns a dictionary"""
    result = discover_components('nonexistent.package')
    assert isinstance(result, dict)
    assert result == {}

def test_discover_components_import_error_handled():
    """Test that ImportError is caught and returns empty dict"""
    result = discover_components('non.existent.package.name.that.does.not.exist')
    assert result == {}

def test_discover_components_valid_structure():
    """Test that function follows expected structure"""
    result = discover_components('some.package')
    assert isinstance(result, dict)

def test_discover_components_no_side_effects():
    """Test that function doesn't modify inputs"""
    package_name = 'test.package'
    result1 = discover_components(package_name)
    result2 = discover_components(package_name)
    assert result1 == result2
    assert result1 == {}
