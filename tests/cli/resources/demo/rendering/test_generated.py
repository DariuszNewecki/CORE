from __future__ import annotations

from unittest.mock import patch

from cli.resources.demo.rendering import build_markdown_report


# ID: 9ef7028e-8bc4-470a-844d-d5bd4bae4a34
def test_build_markdown_report() -> None:
    payload = {
        "verdict": "PASS",
        "run_id": "run-123",
        "assessed_commit": "abc1234",
        "operator_confirmation": "confirmed",
        "finding": {
            "finding_id": "f-1",
            "rule": "R-1",
            "path": "src/foo.py",
            "original_status": "open",
        },
        "proposal": {
            "proposal_id": "p-1",
            "actions": ["edit"],
            "scope_files": ["src/foo.py"],
            "risk": "low",
            "approval_authority": "operator",
            "approver_identity": "alice",
            "finding_ids": ["f-1"],
        },
        "execution": {
            "claimer": "bob",
            "terminal_status": "completed",
            "pre_execution_sha": "aaa",
            "post_execution_sha": "bbb",
            "files_changed": 1,
            "findings_resolved": 1,
        },
        "reaudit": {"clean": True, "match_count": 0},
        "cleanup": {"workspace_removed": True, "retained_path": "/tmp/ws"},
        "assertions": [
            {"name": "A1", "passed": True, "detail": "ok | fine"},
            {"name": "A2", "passed": False, "detail": "bad"},
        ],
        "error": None,
    }

    with patch(
        "cli.resources.demo.rendering._report_payload", return_value=payload
    ) as mock_payload:
        result = build_markdown_report(object(), "confirmed")

    mock_payload.assert_called_once()
    assert isinstance(result, str)
    assert "# CORE — Isolated Consequence-Chain Demo Report" in result
    assert "**Verdict:** PASS" in result
    assert "run-123" in result
    assert "abc1234" in result
    assert "## Finding" in result
    assert "f-1" in result
    assert "## Proposal" in result
    assert "## Execution & consequence" in result
    assert "## Re-audit" in result
    assert "## Cleanup" in result
    assert "Workspace removed." in result
    assert "| A1 | ✅ | ok \\| fine |" in result
    assert "| A2 | ❌ | bad |" in result


import json
from unittest.mock import MagicMock

from cli.resources.demo.rendering import build_json_report


# ID: 4f5e8191-08af-4607-94a1-058f3006637f
def test_build_json_report():
    result = MagicMock()
    payload = {"phase": "demo", "status": "ok", "evidence": ["a", "b"]}

    with patch(
        "cli.resources.demo.rendering._report_payload",
        return_value=payload,
    ) as mock_payload:
        output = build_json_report(result, "strict")

    mock_payload.assert_called_once_with(result, "strict")
    assert output == json.dumps(payload, indent=2)
    assert json.loads(output) == payload


from cli.resources.demo.rendering import render_summary


# ID: 35ba4ebb-96b5-413b-9bfc-6d5784b63395
def test_render_summary() -> None:
    console = MagicMock()
    result = MagicMock()
    result.ok = True
    result.assertions = []

    payload = {
        "run_id": "run-123",
        "assessed_commit": "abc123",
        "finding": {
            "finding_id": "f-1",
            "rule": "rule-x",
            "path": "src/foo.py",
            "original_status": "open",
        },
        "proposal": {
            "proposal_id": "p-1",
            "actions": ["a1"],
            "risk": "low",
            "approval_authority": "policy-eng",
            "approver_identity": "svc-account",
        },
        "execution": {
            "claimer": "claimer-1",
            "terminal_status": "succeeded",
            "pre_execution_sha": "aaa",
            "post_execution_sha": "bbb",
            "files_changed": 2,
        },
        "resolved_finding_status": "closed",
        "reaudit": {"clean": True, "match_count": 0},
        "operator_confirmation": "confirmed",
        "cleanup": {"workspace_removed": True, "retained_path": None},
    }

    with patch(
        "cli.resources.demo.rendering._report_payload",
        return_value=payload,
    ):
        render_summary(console, result, "operator")

    assert console.print.called
