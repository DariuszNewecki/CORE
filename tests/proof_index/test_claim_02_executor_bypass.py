# tests/proof_index/test_claim_02_executor_bypass.py
"""Proof Index claim 2: @atomic_action functions cannot be called outside ActionExecutor.

Standing regression check for docs/proof-index.md claim 2 (#798). A function
decorated with @atomic_action reads a governance token set only by
ActionExecutor.execute(); a direct call finds no token and raises
GovernanceBypassError. This pins the invariant by calling *through* the decorator
(not .__wrapped__, which other tests use to skip the guard) — the mirror of the
doc's "Bypass smoke". If this test stops raising, claim 2 is broken.
"""

from __future__ import annotations

import pytest

from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.governance_token import GovernanceBypassError


async def test_direct_atomic_action_call_raises_governance_bypass() -> None:
    @atomic_action(
        action_id="proof.index.claim2.demo",
        intent="proof-index claim 2 regression check",
        impact=ActionImpact.READ_ONLY,
        policies=[],
    )
    async def _demo(**kwargs: object) -> ActionResult:
        return ActionResult(
            action_id="proof.index.claim2.demo",
            ok=True,
            data={},
            impact=ActionImpact.READ_ONLY,
            duration_sec=0.0,
        )

    with pytest.raises(GovernanceBypassError):
        await _demo()
