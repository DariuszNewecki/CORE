# tests/will/autonomy/test_proposal_risk_vocabulary_g6.py
"""Regression: a flow wrapping a `dangerous`-classified action must compute
`overall_risk == "high"`, never silently collapse to "safe" or "moderate"
(G6 — production-readiness assessment errata, 2026-07-23 correction 1).

Root cause this guards against
-------------------------------
`_compute_flow_risk()` ranks each step's impact against an internal
`risk_levels` dict keyed by the `action_risk.yaml` *input* vocabulary
(`safe`/`moderate`/`dangerous`), then returns the flow's own risk through a
different, ADR-059 D1 *output* vocabulary (`safe`/`moderate`/`high`).
`Proposal.compute_risk()` re-ingests that output-vocabulary string — for a
flow-typed action, or for a nested FLOW step inside `_compute_flow_risk`
itself — and ranks it against a `risk_levels` dict that only recognizes the
*input* vocabulary. `"high"` is not a key in that dict, so the lookup's
default silently returns a lower level:

- Top level (`Proposal.compute_risk`): `risk_levels.get("high", 0)` -> `0`
  ("safe") — a proposal wrapping a flow that contains a dangerous action is
  assessed and auto-approved as "safe", bypassing the human-approval-
  required path entirely.
- Nested (`_compute_flow_risk`'s own recursion): `risk_levels.get("high", 1)`
  -> `1` ("moderate") — an outer flow wrapping a "high"-risk nested flow is
  silently demoted to "moderate".

Both call sites must recognize "dangerous" (input vocabulary) and "high"
(output vocabulary) as the same ranked level — they name one severity in two
vocabularies, not two different severities.
"""

from __future__ import annotations

import pytest

# body.atomic must finish loading before will.autonomy.proposal pulls in its
# registry imports — pre-existing body.atomic <-> will.autonomy circular
# import surfaces during isolated collection otherwise (see the sibling
# test_proposal_compute_risk_flow.py for the same guard).
import body.atomic  # noqa: F401  -- import-order side effect, not a usage
from body.flows.registry import FlowDefinition, FlowStep, StepKind, flow_registry
from will.autonomy.proposal import (
    Proposal,
    ProposalAction,
    ProposalScope,
    _compute_flow_risk,
)


def _register_temp_flow(
    monkeypatch: pytest.MonkeyPatch, flow_id: str, steps: list[FlowStep]
) -> None:
    """Register a synthetic FlowDefinition for the duration of one test.

    No real flow in `.intent/flows/*.yaml` currently contains a
    `dangerous`-classified action (confirmed in the errata's own read-only
    check across all 6 declared flows), so this defect can only be
    reproduced with a synthetic flow — monkeypatched onto the real
    `flow_registry` singleton rather than faked at the module-import level,
    so `_compute_flow_risk`'s real recursion and resolution logic runs
    unmodified.
    """
    flow_def = FlowDefinition(
        flow_id=flow_id, description="synthetic G6 test flow", steps=steps, policies=[]
    )
    original_get = flow_registry.get

    def fake_get(fid: str) -> FlowDefinition | None:
        if fid == flow_id:
            return flow_def
        return original_get(fid)

    monkeypatch.setattr(flow_registry, "get", fake_get)


def test_flow_wrapping_a_dangerous_action_resolves_high(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_compute_flow_risk's own return value for a dangerous-containing flow."""
    _register_temp_flow(
        monkeypatch,
        "flow.g6_test_dangerous",
        [FlowStep(ref_id="test.g6.dangerous_action", kind=StepKind.ACTION)],
    )
    risk_mapping = {"test.g6.dangerous_action": "dangerous"}

    assert _compute_flow_risk("flow.g6_test_dangerous", risk_mapping) == "high"


def test_nested_flow_high_risk_is_not_demoted_to_moderate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An outer flow wrapping a "high"-risk nested flow must stay "high"."""
    _register_temp_flow(
        monkeypatch,
        "flow.g6_inner_dangerous",
        [FlowStep(ref_id="test.g6.dangerous_action", kind=StepKind.ACTION)],
    )
    _register_temp_flow(
        monkeypatch,
        "flow.g6_outer_wraps_inner",
        [FlowStep(ref_id="flow.g6_inner_dangerous", kind=StepKind.FLOW)],
    )
    risk_mapping = {"test.g6.dangerous_action": "dangerous"}

    assert _compute_flow_risk("flow.g6_inner_dangerous", risk_mapping) == "high"
    outer_risk = _compute_flow_risk("flow.g6_outer_wraps_inner", risk_mapping)
    assert outer_risk == "high", (
        "an outer flow wrapping a nested 'high'-risk flow must not be "
        f"silently demoted; got {outer_risk!r}"
    )


def test_proposal_wrapping_dangerous_flow_computes_high_and_requires_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: Proposal.compute_risk() must not auto-approve this proposal.

    This is the exact scenario the errata traced live: a proposal whose only
    action is a flow containing a dangerous-classified step must come out
    "high" and require human approval — not "safe" with approval_required
    False.
    """
    _register_temp_flow(
        monkeypatch,
        "flow.g6_test_dangerous",
        [FlowStep(ref_id="test.g6.dangerous_action", kind=StepKind.ACTION)],
    )
    monkeypatch.setattr(
        "shared.infrastructure.intent.action_risk.load_action_risk",
        lambda: {"test.g6.dangerous_action": "dangerous"},
    )

    proposal = Proposal(
        goal="G6 regression: flow wrapping a dangerous action",
        actions=[ProposalAction(flow_id="flow.g6_test_dangerous", order=0)],
        scope=ProposalScope(files=["src/example.py"]),
    )
    proposal.compute_risk()

    assert proposal.risk is not None
    assert proposal.risk.overall_risk == "high", (
        "a flow wrapping a dangerous action must compute overall_risk "
        f"'high'; got {proposal.risk.overall_risk!r} — this proposal would "
        "auto-approve and bypass human review (G6)."
    )
    assert proposal.approval_required is True, (
        "overall_risk 'high' must require human approval "
        f"(got approval_required={proposal.approval_required!r})"
    )
