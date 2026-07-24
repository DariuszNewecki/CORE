# tests/cli/resources/demo/test_rendering.py
"""D12 truthful-evidence rendering tests (ADR-155 U11/U12/U14)."""

from __future__ import annotations

import json

from cli.resources.demo.rendering import (
    _PROOF_STATEMENT,
    build_json_report,
    build_markdown_report,
    render_summary,
)

from .conftest import FINDING_ID, PROPOSAL_ID


# ── U14: Markdown and JSON carry identical identities ──────────────────────────


# ID: 87a7602c-24d7-4eda-a492-904d76b2eb4d
def test_markdown_and_json_share_identities(passing_result) -> None:
    md = build_markdown_report(passing_result, "human")
    payload = json.loads(build_json_report(passing_result, "human"))

    for token in (passing_result.run_id, FINDING_ID, PROPOSAL_ID, "deadbeef"):
        assert token in md, f"{token} missing from Markdown"

    assert payload["run_id"] == passing_result.run_id
    assert payload["finding"]["finding_id"] == FINDING_ID
    assert payload["proposal"]["proposal_id"] == PROPOSAL_ID
    assert payload["assessed_commit"] == "deadbeef"
    # Same identities in both surfaces (U14 matching-identity requirement).
    assert payload["proposal"]["proposal_id"] in md
    assert payload["finding"]["finding_id"] in md


# ── U11: approval honesty ──────────────────────────────────────────────────────


# ID: aab2259b-f2e2-408e-8c55-a50b7e2afdac
def test_approval_rendered_as_policy_authority_not_human(passing_result) -> None:
    md = build_markdown_report(passing_result, "human")
    payload = json.loads(build_json_report(passing_result, "human"))

    assert payload["proposal"]["approval_authority"] == "risk_classification.safe_auto_approval"
    assert payload["proposal"]["approver_identity"] == "autonomous_self_promote"
    # The operator confirmation is a SEPARATE field, never the approver.
    assert payload["operator_confirmation"] == "human"
    assert payload["proposal"]["approver_identity"] != payload["operator_confirmation"]

    lowered = md.lower()
    assert "risk_classification.safe_auto_approval" in md
    assert "human approved" not in lowered
    assert "approved by the operator" not in lowered
    assert "operator approved" not in lowered


# ID: 78df9679-6a71-4fa0-b42b-3622dd25cf96
def test_simulated_confirmation_is_labelled(passing_result) -> None:
    payload = json.loads(build_json_report(passing_result, "simulated"))
    assert payload["operator_confirmation"] == "simulated"
    assert "simulated" in build_markdown_report(passing_result, "simulated")


# ── Proof statement present (D12) ──────────────────────────────────────────────


# ID: 96216fea-496d-4a7a-86c9-85f85878458f
def test_proof_statement_present(passing_result) -> None:
    md = build_markdown_report(passing_result, "human")
    payload = json.loads(build_json_report(passing_result, "human"))
    assert _PROOF_STATEMENT in md
    assert payload["proof_statement"] == _PROOF_STATEMENT
    assert "not a production-readiness attestation" in _PROOF_STATEMENT


# ── U12: failure renders truthfully, no success thesis ────────────────────────


# ID: d71d66e4-c8a9-431a-b883-2a0bac8d3d40
def test_failing_result_reports_failure_and_retained_path(failing_result) -> None:
    md = build_markdown_report(failing_result, "simulated")
    payload = json.loads(build_json_report(failing_result, "simulated"))

    assert payload["verdict"] == "failed"
    assert "passed" != payload["verdict"]
    # The failed assertion is surfaced, not hidden.
    assert any(
        a["name"] == "D10.6_execution_reaches_completed" and not a["passed"]
        for a in payload["assertions"]
    )
    # Missing chain evidence surfaces as null, not a fabricated placeholder.
    assert payload["execution"] is None
    # Retained-workspace path is reported (D11).
    assert payload["cleanup"]["workspace_removed"] is False
    assert "run-fail" in payload["cleanup"]["retained_path"]
    assert "❌" in md


# ── render_summary does not raise and honours the verdict ─────────────────────


# ID: 14f220c1-a6a1-493d-8524-617bef3995f9
def test_render_summary_runs(passing_result, failing_result) -> None:
    from rich.console import Console

    console = Console(record=True, width=100)
    render_summary(console, passing_result, "human")
    out = console.export_text()
    assert "PASSED" in out
    assert "risk_classification.safe_auto_approval" in out
    assert "operator confirm" in out

    console2 = Console(record=True, width=100)
    render_summary(console2, failing_result, "simulated")
    out2 = console2.export_text()
    assert "FAILED" in out2
    assert "RETAINED" in out2
