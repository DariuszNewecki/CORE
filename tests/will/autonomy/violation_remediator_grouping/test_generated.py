from __future__ import annotations

from unittest.mock import patch

from will.autonomy.violation_remediator_grouping import log_delegated


# ID: bee9d805-78a6-4053-b489-57097826caf9
def test_log_delegated():
    delegate = [
        {
            "id": "entry-123",
            "payload": {
                "check_id": "RULE_001",
                "file_path": "src/foo/bar.py",
            },
            "_map_entry": {"description": "Requires human review"},
        },
        {
            "entry_id": "entry-456",
            "payload": {
                "rule": "RULE_002",
                "file_path": "src/baz/qux.py",
            },
            "_map_entry": {"description": "Needs decision"},
        },
    ]

    with patch("will.autonomy.violation_remediator_grouping.logger") as mock_logger:
        log_delegated(delegate)

    assert mock_logger.info.call_count == 2

    first_call = mock_logger.info.call_args_list[0]
    first_args = first_call.args
    assert first_args[1] == "RULE_001"
    assert first_args[2] == "src/foo/bar.py"
    assert first_args[3] == "Requires human review"
    assert first_args[4] == "entry-123"

    second_call = mock_logger.info.call_args_list[1]
    second_args = second_call.args
    assert second_args[1] == "RULE_002"
    assert second_args[2] == "src/baz/qux.py"
    assert second_args[3] == "Needs decision"
    assert second_args[4] == "entry-456"



from will.autonomy.violation_remediator_grouping import group_findings


# ID: efe6d277-c428-412b-bbfe-fccc32219efa
def test_group_findings():
    finding_rule = {"payload": {"check_id": "rule.a", "file_path": "src/foo.py"}}
    finding_flow = {"payload": {"check_id": "flow.b"}}
    finding_delegate = {"payload": {"check_id": "delegate.c"}}
    finding_unmappable = {"payload": {"rule": "unknown.d"}}

    remediation_map = {
        "rule.a": {"status": "ACTIVE", "ref_id": "REF-1", "ref_kind": "rule"},
        "flow.b": {"status": "ACTIVE", "ref_id": "REF-2", "ref_kind": "flow"},
        "delegate.c": {"status": "DELEGATE", "ref_id": "REF-3", "ref_kind": "delegate"},
    }

    with patch("will.autonomy.violation_remediator_grouping.logger") as mock_logger:
        groups = group_findings(
            [finding_rule, finding_flow, finding_delegate, finding_unmappable],
            remediation_map,
        )

    expected_rule_key = ("REF-1", "src/foo.py")
    expected_flow_key = ("REF-2", None)

    assert groups.action_groups[expected_rule_key] == [finding_rule]
    assert groups.action_groups[expected_flow_key] == [finding_flow]
    assert groups.delegate == [finding_delegate]
    assert finding_delegate["_map_entry"] == remediation_map["delegate.c"]
    assert groups.unmappable == [finding_unmappable]
    assert groups.ref_kinds["REF-1"] == "rule"
    assert groups.ref_kinds["REF-2"] == "flow"
    mock_logger.debug.assert_called_once()
