# src/will/autonomy/lane_service.py

"""
Assisted Remediation Lane service (ADR-109 D1/D5, issue #652).

Will-layer facade for the external-agent contract. The lane lets a delegated
finding (`indeterminate` + `human`) be worked by an external agent + governor
through human-gated multi-file proposals, instead of rotting in the inbox.

This service is the API↔Body seam for the lane: the API routes through it
(API → Will), and it delegates the actual blackboard reads/writes to Body via
the service_registry — the pattern `must_delegate_to_body` endorses and that
ProposalService already uses. Keeping lane logic here (rather than in API
handlers) is also what the gate-location decision (#652) requires: the API
surface stays thin, orchestration lives in Will.

For now it covers the read side (`list_delegated_findings`); the `claim` /
`propose` / `validate` orchestration lands here in subsequent increments.
"""

from __future__ import annotations

from typing import Any

from body.services.service_registry import service_registry
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 2b0af18e-484a-449f-af56-5cace4e6efee
class LaneService:
    """Facade over the assisted-lane work queue and proposal lifecycle.

    Stateless: each call acquires the BlackboardService from the registry,
    which owns its own session. Mirrors ProposalService's delegation shape.
    """

    # ID: 2a9692eb-9b24-448b-a1de-4cd586846289
    async def list_delegated_findings(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the delegated findings awaiting assisted remediation.

        Delegates to the canonical governor-inbox predicate
        (`indeterminate` + `human`) on the BlackboardService query layer, so
        the lane queue cannot drift from the dashboard inbox panel.
        """
        bb_service = await service_registry.get_blackboard_service()
        return await bb_service.fetch_delegated_findings(limit=limit)
