from __future__ import annotations

from will.autonomy.proposal_lineage import proposal_lineage


# ID: d48f9a13-8cd8-4700-bc65-d5054dc4f8a5
def test_proposal_lineage():
    assert proposal_lineage({"assisted_lane": True}) == "assisted_lane"
    assert proposal_lineage({"proposal_origin": "ceremony"}) == "ceremony"
    assert proposal_lineage({}) == "autonomous"
    assert proposal_lineage(None) == "autonomous"
