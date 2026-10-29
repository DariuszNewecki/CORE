from __future__ import annotations

from unittest.mock import MagicMock

from mind.governance.rule_findings import content_not_evaluated_finding


# ID: 09f66db3-2be4-4105-a207-d0d3d1b50b5c
def test_content_not_evaluated_finding():
    rule = MagicMock()
    rule.rule_id = "R001"
    rule.engine = "policy_engine"
    rule.policy_id = "POL-42"

    not_evaluated = [
        ("src/a.py", "decode_error"),
        ("src/b.py", "binary_content"),
        ("src/c.py", "decode_error"),
    ]

    finding = content_not_evaluated_finding(rule, not_evaluated)

    assert finding.check_id == "R001.content_not_evaluated"
    assert finding.context["finding_type"] == "CONTENT_NOT_EVALUATED"
    assert finding.context["engine"] == "policy_engine"
    assert finding.context["policy_id"] == "POL-42"
    assert finding.context["file_count"] == 3
    assert finding.context["sample_files"] == ["src/a.py", "src/b.py", "src/c.py"]
    assert finding.context["reasons"] == ["binary_content", "decode_error"]
    assert "3 file(s)" in finding.message



from mind.governance.rule_findings import transient_llm_failure_finding


# ID: 049e5a84-ec49-40c9-b6ea-9122520ba007
def test_transient_llm_failure_finding():
    rule = MagicMock()
    rule.rule_id = "RULE-001"
    rule.engine = "llm_gate"

    failures = [
        ("src/a.py", "timeout"),
        ("src/b.py", "rate limited"),
        ("src/c.py", "timeout"),
    ]

    finding = transient_llm_failure_finding(rule, failures)

    assert finding.check_id == "RULE-001"
    assert finding.file_path == "none"
    assert finding.context["finding_type"] == "LLM_TRANSIENT_FAILURE"
    assert finding.context["engine_id"] == "llm_gate"
    assert finding.context["failure_count"] == 3
    assert finding.context["sample_files"] == ["src/a.py", "src/b.py", "src/c.py"]
    assert finding.context["sample_errors"] == [
        {"file": "src/a.py", "error": "timeout"},
        {"file": "src/b.py", "error": "rate limited"},
        {"file": "src/c.py", "error": "timeout"},
    ]
    assert finding.context["unique_error_messages"] == ["rate limited", "timeout"]
    assert "RULE-001" in finding.message
    assert "3 file(s)" in finding.message
    assert "2 unique error(s)" in finding.message
