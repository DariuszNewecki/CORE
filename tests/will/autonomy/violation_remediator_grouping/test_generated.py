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
