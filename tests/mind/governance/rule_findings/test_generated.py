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
