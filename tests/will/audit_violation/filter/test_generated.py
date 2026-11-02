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


from will.audit_violation.filter import is_autonomously_remediable_target


# ID: e47aff14-7c7f-473f-9c41-6501becbcd66
def test_is_autonomously_remediable_target():
    assert is_autonomously_remediable_target("src/will/module.py") is True




# ID: 458b09f3-546c-4638-bb5a-f7db274149ce
def test_filter_actionable_violations():
    from will.audit_violation.filter import filter_actionable_violations

    violations = [
        # Should be kept
        {"file_path": "src/foo.py", "rule_id": "purity.no_dead_code"},
        {"file_path": "src/bar.py", "rule_id": "style.line_length"},
        # Drop: sentinel file path
        {"file_path": "System", "rule_id": "purity.no_dead_code"},
        # Drop: symbol-pair file path
        {"file_path": "__symbol_pair__xyz", "rule_id": "purity.no_dead_code"},
        # Drop: malformed rule_id containing "/"
        {"file_path": "src/baz.py", "rule_id": "enforcement/mappings/arch/foo.yaml"},
    ]

    # ID: 7ff0a514-d853-44a5-84d2-0f3a785c44b0
    def fake_is_remediable(path: str) -> bool:
        return path.endswith(".py")

    with patch(
        "will.audit_violation.filter.is_autonomously_remediable_target",
        side_effect=fake_is_remediable,
    ):
        result = filter_actionable_violations(violations)

    assert result == [
        {"file_path": "src/foo.py", "rule_id": "purity.no_dead_code"},
        {"file_path": "src/bar.py", "rule_id": "style.line_length"},
    ]
