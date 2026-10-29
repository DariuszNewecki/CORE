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


from mind.governance.rule_findings import enforcement_failure_finding


# ID: b5140429-b79f-4f5a-b93d-7fd062484cb3
def test_enforcement_failure_finding():
    rule = MagicMock()
    rule.rule_id = "RULE_001"
    rule.engine = "pytest"
    rule.policy_id = "POLICY_42"

    error = RuntimeError("boom")

    finding = enforcement_failure_finding(
        rule, "/abs/path/file.py", "src/file.py", error
    )

    assert finding.check_id == "RULE_001.enforcement_failure"
    assert finding.severity.name == "BLOCK"
    assert "ENFORCEMENT_FAILURE" in finding.message
    assert "/abs/path/file.py" in finding.message
    assert "boom" in finding.message
    assert finding.file_path == "src/file.py"
    assert finding.context["finding_type"] == "ENFORCEMENT_FAILURE"
    assert finding.context["engine"] == "pytest"
    assert finding.context["policy_id"] == "POLICY_42"
    assert finding.context["exception_type"] == "RuntimeError"
    assert finding.context["exception_message"] == "boom"



from mind.governance.rule_findings import llm_stub_finding


# ID: 770f2769-0d58-4667-9173-701aa761f634
def test_llm_stub_finding():
    rule = MagicMock()
    rule.rule_id = "rule-abc"
    rule.engine = "llm_gate"

    finding = llm_stub_finding(rule)

    assert finding.check_id == "rule-abc"
    assert finding.file_path == "none"
    assert finding.context["engine_id"] == "llm_gate"
    assert finding.context["stub"] is True
    assert finding.context["reason"] == "no_llm_client"
    assert "rule-abc" in finding.message
    assert "llm_gate" in finding.message
