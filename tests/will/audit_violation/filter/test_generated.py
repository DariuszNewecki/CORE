from __future__ import annotations

from unittest.mock import patch


# ID: b9f25f10-0118-492a-a96b-395c287ad74f
def test_non_remediable_violations():
    from will.audit_violation.filter import non_remediable_violations

    violations = [
        {"file_path": "src/real.py", "rule_id": "E501"},  # unremediable -> kept
        {"file_path": "System", "rule_id": "E501"},  # sentinel -> dropped
        {"file_path": "src/other.py", "rule_id": "a/b"},  # bad rule id -> dropped
        {"file_path": "__symbol_pair__x", "rule_id": "E1"},  # placeholder -> dropped
        {"file_path": "src/remediable.py", "rule_id": "W1"},  # remediable -> dropped
    ]

    with patch(
        "will.audit_violation.filter.is_autonomously_remediable_target",
        side_effect=lambda p: p == "src/remediable.py",
    ):
        result = non_remediable_violations(violations)

    assert result == [
        {"file_path": "src/real.py", "rule_id": "E501"},
    ]
