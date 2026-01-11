"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/policy_analyzer.py
- Symbol: AtomicRule
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:28:58
"""

from mind.governance.policy_analyzer import AtomicRule


# Detected return type: AtomicRule is a dataclass/class constructor. Tests will verify attribute assignment and equality.


def test_atomicrule_initialization():
    """Test basic initialization with all attributes."""
    rule = AtomicRule(
        source_file="/full/path/to/constitution.txt",
        principle_id="PRINCIPLE_1",
        rule_text="Do not harm others.",
        scope=["all_agents", "human_interaction"],
        enforcement_method="self_correction",
    )
    assert rule.source_file == "/full/path/to/constitution.txt"
    assert rule.principle_id == "PRINCIPLE_1"
    assert rule.rule_text == "Do not harm others."
    assert rule.scope == ["all_agents", "human_interaction"]
    assert rule.enforcement_method == "self_correction"


def test_atomicrule_equality():
    """Test that two instances with same data are equal."""
    rule1 = AtomicRule(
        source_file="/path/file.txt",
        principle_id="ID1",
        rule_text="Text",
        scope=["scope1"],
        enforcement_method="method",
    )
    rule2 = AtomicRule(
        source_file="/path/file.txt",
        principle_id="ID1",
        rule_text="Text",
        scope=["scope1"],
        enforcement_method="method",
    )
    assert rule1.source_file == rule2.source_file
    assert rule1.principle_id == rule2.principle_id
    assert rule1.rule_text == rule2.rule_text
    assert rule1.scope == rule2.scope
    assert rule1.enforcement_method == rule2.enforcement_method


def test_atomicrule_with_empty_scope():
    """Test initialization with an empty scope list."""
    rule = AtomicRule(
        source_file="/file.txt",
        principle_id="P1",
        rule_text="Rule text.",
        scope=[],
        enforcement_method="none",
    )
    assert rule.scope == []


def test_atomicrule_with_multiline_rule_text():
    """Test that rule_text can contain newlines and special characters."""
    multiline_text = "First line.\nSecond line with tab\there.\nThird line."
    rule = AtomicRule(
        source_file="/file.txt",
        principle_id="P2",
        rule_text=multiline_text,
        scope=["global"],
        enforcement_method="log",
    )
    assert rule.rule_text == multiline_text


def test_atomicrule_with_unicode_in_text():
    """Test handling of Unicode characters, including the ellipsis."""
    unicode_text = "Wait for response… then proceed. Signal ✓ received."
    rule = AtomicRule(
        source_file="/unicode/file.txt",
        principle_id="UNICODE_TEST",
        rule_text=unicode_text,
        scope=["test"],
        enforcement_method="review",
    )
    assert rule.rule_text == unicode_text
