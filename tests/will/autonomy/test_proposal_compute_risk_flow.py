"""Regression: Proposal.compute_risk() must resolve action impact from the
governed action_risk mapping, not from registry-overlay state.

Root cause this guards against
------------------------------
ActionDefinition.impact_level is populated *only* as a side-effect of
ActionExecutor.__init__ (executor.apply_risk_config). TestRemediatorWorker
computes proposal risk before any executor exists in its process, so every
action read an empty impact_level. The two risk-lookup defaults diverged —
direct actions defaulted to "safe" (0), flow steps defaulted to "moderate"
(1) — so flow-based proposals (flow.build_tests) computed "moderate",
flipped approval_required=True, and stuck in DRAFT, silently stalling the
autonomous test-gen loop. ADR-008: impact_level is governed externally;
risk computation must read it from action_risk.yaml directly.

These tests deliberately do NOT instantiate an ActionExecutor — they
reproduce the worker's pre-executor context. They pass only if impact is
sourced from the governed mapping.
"""

from __future__ import annotations

# body.atomic must finish loading before will.autonomy.proposal pulls in its
# registry imports — pre-existing body.atomic ↔ will.autonomy circular import
# surfaces during isolated collection otherwise.
import body.atomic  # noqa: F401  -- import-order side effect, not a usage
from will.autonomy.proposal import (
    Proposal,
    ProposalAction,
    ProposalScope,
    _compute_flow_risk,
    _resolve_impact,
)


_BUILD_TESTS_FLOW = "flow.build_tests"


# ID: 6f3d2a1c-9b4e-47d8-8a52-1e6c0f9b7d34
def test_build_tests_flow_risk_is_safe_without_executor_init() -> None:
    """flow.build_tests must resolve to "safe" on a fresh registry.

    All of its steps (build.tests, fix.imports, fix.headers, fix.format,
    test.sandbox_validate) are classified "safe" in action_risk.yaml, so the
    flow's max impact is "safe" — regardless of whether an ActionExecutor has
    overlaid impact_level onto the registry yet.
    """
    from shared.infrastructure.intent.action_risk import load_action_risk

    risk = _compute_flow_risk(_BUILD_TESTS_FLOW, load_action_risk())
    assert risk == "safe", (
        f"{_BUILD_TESTS_FLOW} should compute 'safe' from the governed mapping "
        f"(all steps are safe); got {risk!r}. A 'moderate' result means impact "
        f"is being read from empty registry-overlay state again."
    )


# ID: 2c8e1f4a-7d6b-4e93-b1a0-5f2d9c8a3e61
def test_build_tests_proposal_auto_approves() -> None:
    """A test-gen proposal must not require approval — it must self-promote.

    This is the end-to-end condition that was broken: approval_required True
    left the proposal stuck in DRAFT and the autonomous loop never executed.
    """
    proposal = Proposal(
        goal="Autonomous test remediation: flow.build_tests",
        actions=[
            ProposalAction(
                flow_id=_BUILD_TESTS_FLOW,
                parameters={
                    "source_file": "src/will/workers/circuit_breaker.py",
                    "write": True,
                },
                order=0,
            )
        ],
        scope=ProposalScope(files=["src/will/workers/circuit_breaker.py"]),
        created_by="test_remediator_worker",
    )
    proposal.compute_risk()

    assert proposal.risk is not None
    assert proposal.risk.overall_risk == "safe", (
        f"expected overall_risk 'safe'; got {proposal.risk.overall_risk!r}"
    )
    assert proposal.approval_required is False, (
        "a safe test-gen proposal must auto-approve (approval_required=False); "
        "True reproduces the DRAFT-stall regression."
    )


# ID: 9a4b7e2d-1c8f-4a06-93b5-6d0e2f7c1b48
def test_resolve_impact_fails_closed_for_unmapped_action() -> None:
    """An action_id absent from the governed mapping must resolve "moderate".

    Fail-closed: an unclassified action is never silently treated as safe.
    """
    assert _resolve_impact("totally.unmapped.action", {}) == "moderate"
    assert _resolve_impact("known.safe", {"known.safe": "safe"}) == "safe"
