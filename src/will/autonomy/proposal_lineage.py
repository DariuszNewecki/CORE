# src/will/autonomy/proposal_lineage.py
"""
Proposal lineage discriminator (ADR-154 D3).

Three lanes create human-gated DRAFT proposals from `constitutional_constraints`
today: the legacy mapped-remediation autonomous lane (no marker — the
historical default), the ADR-109 external-assisted lane (`assisted_lane: True`),
and the ADR-154 ceremony lane (`proposal_origin: "ceremony"`).

Before this module, `constitutional_constraints.get("assisted_lane")` was the
*sole* discriminator: "truthy" meant assisted-lane, anything else meant
autonomous. That binary read is wrong for ceremony proposals, which need
distinct behavior from BOTH other lanes on explicit governor rejection (they
must land at indeterminate+human, like assisted-lane, but via a different
Body operation because their findings' resolution_mechanism is 'reaudit' not
'human') while sharing the autonomous lane's revival predicate on execution
failure (the ADR-038 circuit-breaker path, because ceremony findings are
born resolution_mechanism='reaudit' and must stay that way while deferred).
A single boolean cannot express "same as X here, same as Y there" — hence
this explicit three-way lineage read, used identically by every call site
that used to branch on the assisted_lane flag alone.
"""

from __future__ import annotations

from typing import Any, Literal


ProposalLineage = Literal["assisted_lane", "ceremony", "autonomous"]

_ORIGIN_KEY = "proposal_origin"
_CEREMONY_ORIGIN = "ceremony"


# ID: 9110f515-eb44-42b1-a91a-462cfad67b50
def proposal_lineage(
    constitutional_constraints: dict[str, Any] | None,
) -> ProposalLineage:
    """Classify a proposal's lineage from its constitutional_constraints.

    Read order matters only in that both markers should never co-occur in
    practice (a proposal is constructed by exactly one lane's factory call);
    assisted_lane is checked first purely because it is the older, more
    load-bearing marker.
    """
    constraints = constitutional_constraints or {}
    if constraints.get("assisted_lane"):
        return "assisted_lane"
    if constraints.get(_ORIGIN_KEY) == _CEREMONY_ORIGIN:
        return "ceremony"
    return "autonomous"
