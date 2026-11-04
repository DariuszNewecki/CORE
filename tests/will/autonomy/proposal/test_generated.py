from __future__ import annotations

from will.autonomy.proposal import ProposalConsequence


# ID: e5c55301-71ea-4f8f-808c-29e458816949
def test_ProposalConsequence():
    consequence = ProposalConsequence(
        proposal_id="prop-123",
        pre_execution_sha="abc123",
        post_execution_sha="def456",
        files_changed=[{"path": "src/will/autonomy/proposal.py"}],
        findings_resolved=["F-1", "F-2"],
        authorized_by_rules=["ADR-133"],
    )

    assert consequence.proposal_id == "prop-123"
    assert consequence.pre_execution_sha == "abc123"
    assert consequence.post_execution_sha == "def456"
    assert consequence.files_changed == [{"path": "src/will/autonomy/proposal.py"}]
    assert consequence.findings_resolved == ["F-1", "F-2"]
    assert consequence.authorized_by_rules == ["ADR-133"]
    assert consequence.recorded_at is None

    minimal = ProposalConsequence(proposal_id="prop-456")
    assert minimal.pre_execution_sha is None
    assert minimal.post_execution_sha is None
    assert minimal.files_changed == []
    assert minimal.findings_resolved == []
    assert minimal.authorized_by_rules == []
    assert minimal.recorded_at is None

    # default_factory must yield independent list instances per instance
    assert minimal.files_changed is not consequence.files_changed
