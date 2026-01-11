"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/schemas.py
- Symbol: ConstitutionalPrinciple
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:59:46
"""

from mind.governance.schemas import ConstitutionalPrinciple


# Detected return type: ConstitutionalPrinciple is a class, so tests will instantiate and validate it.


def test_constitutional_principle_instantiation():
    """Test basic instantiation with all required fields."""
    principle = ConstitutionalPrinciple(
        principle_id="TEST_ID_001",
        statement="All systems shall prioritize user safety.",
        rationale="Safety is a fundamental requirement for trust.",
        scope=["system_behavior", "output_generation"],
        enforcement_method="automated_monitoring",
        enforcement_parameters={"threshold": 0.95, "action": "log"},
        source_document="Core Safety Principles v2.1",
    )
    assert principle.principle_id == "TEST_ID_001"
    assert principle.statement == "All systems shall prioritize user safety."
    assert principle.rationale == "Safety is a fundamental requirement for trust."
    assert principle.scope == ["system_behavior", "output_generation"]
    assert principle.enforcement_method == "automated_monitoring"
    assert principle.enforcement_parameters == {"threshold": 0.95, "action": "log"}
    assert principle.source_document == "Core Safety Principles v2.1"


def test_constitutional_principle_with_empty_scope_and_params():
    """Test instantiation with empty list and dict."""
    principle = ConstitutionalPrinciple(
        principle_id="TEST_ID_002",
        statement="A statement.",
        rationale="A rationale.",
        scope=[],
        enforcement_method="none",
        enforcement_parameters={},
        source_document="Test Doc",
    )
    assert principle.scope == []
    assert principle.enforcement_parameters == {}


def test_constitutional_principle_field_types():
    """Verify the types of the class fields are as expected."""
    principle = ConstitutionalPrinciple(
        principle_id="id",
        statement="stmt",
        rationale="rat",
        scope=["a"],
        enforcement_method="method",
        enforcement_parameters={"key": "value"},
        source_document="doc",
    )
    assert isinstance(principle.principle_id, str)
    assert isinstance(principle.statement, str)
    assert isinstance(principle.rationale, str)
    assert isinstance(principle.scope, list)
    assert all(isinstance(item, str) for item in principle.scope)
    assert isinstance(principle.enforcement_method, str)
    assert isinstance(principle.enforcement_parameters, dict)
    assert isinstance(principle.source_document, str)
