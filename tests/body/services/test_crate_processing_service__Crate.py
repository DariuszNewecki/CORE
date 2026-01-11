"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/body/services/crate_processing_service.py
- Symbol: Crate
- Status: verified_in_sandbox
- Generated: 2026-01-11 03:07:47
"""

import pytest
from pathlib import Path
from body.services.crate_processing_service import Crate

# TARGET CODE ANALYSIS:
# The provided Crate class is a simple data class with two attributes: 'path' and 'manifest'.
# It is not a function and does not contain any async methods.
# Therefore, tests will be synchronous and focus on instantiation and attribute access.

def test_crate_initialization():
    """Test that a Crate object can be instantiated with correct attributes."""
    test_path = Path("/full/path/to/file.txt")
    test_manifest = {"name": "test", "version": 1}
    crate = Crate(path=test_path, manifest=test_manifest)

    assert crate.path == test_path
    assert crate.manifest == test_manifest

def test_crate_attributes_are_mutable():
    """Test that the Crate's attributes can be accessed and are the passed values."""
    test_path = Path("/another/full/path")
    test_manifest = {"key": "value", "list": [1, 2, 3]}
    crate = Crate(path=test_path, manifest=test_manifest)

    # Check path attribute
    assert crate.path == test_path
    # Check manifest attribute
    assert crate.manifest == test_manifest
    # Verify manifest content is equal
    assert crate.manifest["key"] == "value"
    assert crate.manifest["list"] == [1, 2, 3]

def test_crate_with_empty_manifest():
    """Test Crate initialization with an empty manifest dictionary."""
    test_path = Path("/full/path/empty.manifest")
    empty_manifest = {}
    crate = Crate(path=test_path, manifest=empty_manifest)

    assert crate.path == test_path
    assert crate.manifest == {}
    assert len(crate.manifest) == 0

def test_crate_path_is_path_object():
    """Ensure the 'path' attribute is a Path object and comparable."""
    from pathlib import Path
    test_path_str = "/full/absolute/path"
    crate = Crate(path=Path(test_path_str), manifest={})

    assert isinstance(crate.path, Path)
    assert crate.path == Path(test_path_str)
    # Check that it is not incorrectly a string
    assert not isinstance(crate.path, str)
