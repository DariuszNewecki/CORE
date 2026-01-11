"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/audit_types.py
- Symbol: AuditCheckMetadata
- Status: 4 tests passed, some failed
- Passing tests: test_audit_check_metadata_creation_with_minimal_fields, test_audit_check_metadata_with_empty_strings, test_audit_check_metadata_with_none_category, test_audit_check_metadata_with_whitespace_in_strings
- Generated: 2026-01-11 02:00:51
"""

from mind.governance.audit_types import AuditCheckMetadata


def test_audit_check_metadata_creation_with_minimal_fields():
    """Test creation with only required fields."""
    metadata = AuditCheckMetadata(id="test_check", name="Test Check Name")
    assert metadata.id == "test_check"
    assert metadata.name == "Test Check Name"
    assert metadata.category is None
    assert metadata.fix_hint is None
    assert metadata.default_severity is None


def test_audit_check_metadata_with_empty_strings():
    """Test creation with empty string values (should be allowed)."""
    metadata = AuditCheckMetadata(id="", name="", category="", fix_hint="")
    assert metadata.id == ""
    assert metadata.name == ""
    assert metadata.category == ""
    assert metadata.fix_hint == ""
    assert metadata.default_severity is None


def test_audit_check_metadata_with_none_category():
    """Test explicit None for category field."""
    metadata = AuditCheckMetadata(
        id="no_category", name="No Category Check", category=None, fix_hint="some fix"
    )
    assert metadata.id == "no_category"
    assert metadata.name == "No Category Check"
    assert metadata.category is None
    assert metadata.fix_hint == "some fix"


def test_audit_check_metadata_with_whitespace_in_strings():
    """Test with strings containing various whitespace."""
    metadata = AuditCheckMetadata(
        id="  check_id  ",
        name="  Check Name with\tTabs  ",
        category="  category  ",
        fix_hint="fix\nwith\nnewlines",
    )
    assert metadata.id == "  check_id  "
    assert metadata.name == "  Check Name with\tTabs  "
    assert metadata.category == "  category  "
    assert metadata.fix_hint == "fix\nwith\nnewlines"
