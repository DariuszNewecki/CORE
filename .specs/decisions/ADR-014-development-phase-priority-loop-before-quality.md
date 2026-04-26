# ADR-014 — Development-Phase Priority: Loop Liveness Before Artifact Quality

**Date:** 2026-04-26
**Status:** Accepted
**Commits:** pending

## Decision

During CORE's development phase, generation-loop liveness takes priority over individual artifact quality. As the first application of this priority: reclassify `build.tests` from `impact_level="moderate"` to `impact_level="safe"`.

**Change site:** `src/body/atomic/build_tests_action.py`, line 1289 (`@register_action` decorator). Single-literal edit. The `@atomic_action` decorator on the same function is unaffected — it carries a different field (`impact=ActionImpact.WRITE_CODE`) governing action shape, not approval gating.

## Rationale

The Convergence Principle is a rate equation: resolutions must exceed creations. A loop that produces zero outputs has zero resolution rate — not "high-quality autonomy," no autonomy. Quality is observable and improvable only on a moving system; optimizing quality on a stalled queue is optimizing the wrong thing.

The diagnostic on issue #152 (2026-04-26) found 10 `build.tests` proposals stuck in `draft` for up to 2 days. Cause: `risk.overall_risk = "moderate"` triggers `approval_required = True`, but no human or automated approver acts on this class. The approval gate, in its current placement, has no artifact to inspect — LLM generation happens at `executing`, not `draft`. The moderate classification was protecting an option (human approval) the system never used, against a risk (LLM hallucination) the gate could not have caught at that point in the lifecycle.

Priority order during development phase:

1. **Liveness** — the loop runs.
2. **Productivity** — the loop produces outputs at a rate exceeding creation.
3. **Quality** — the outputs the loop produces are correct.

This is sequential, not parallel.

## What this does not remove

Three commit-time gates remain in place: `ConservationGate → IntentGuard → Canary`. `TestRunnerSensor` continues to run generated tests and surface failures. A test that fails to run, fails to import, or violates `.intent/` rules is still caught downstream.

What is **not** caught at any layer: a test that runs, passes, and asserts the wrong thing. This is acknowledged residual risk for the development phase.

## Revisit triggers

This classification reverts when any of the following becomes true:

- A measured hallucination rate on generated tests is established and exceeds an agreed threshold.
- Test-suite signal contamination (passing tests masking real failures) is observed in audit output.
- CORE moves out of development phase (first external deployment, first regulated-environment use).
- `impact_level` is constitutionalized per ADR-008, at which point this classification migrates to `.intent/enforcement/config/action_risk.yaml`.

Quality measurement is a follow-on item, not a pre-condition. Without measurement, "we'll change it back when CORE gets smarter" does not survive the next 50 sessions.

## Relationship to ADR-008

ADR-008 (parked) flagged that `impact_level` declarations belong in `.intent/`, not in `@register_action` decorators. This ADR makes a `src/`-side change that ADR-008 would prefer to see made in `.intent/`. The G4 leak is acknowledged debt, not a new violation. When ADR-008 is unparked and `impact_level` is constitutionalized, this `safe` classification migrates with it.

ADR-008 itself records a prior in-`src/` reclassification (`fix.placeholders` from `moderate` to `safe`) following the same pattern. This ADR is the second instance.

## Consequence

`build.tests` proposals are created in approved state and execute through `ProposalConsumerWorker` without human gate. The 10 currently-stuck drafts likely remain stuck — `approval_required` is set at create time and persisted on the row. New `build.tests` proposals from this point forward auto-approve.

The empirical question — whether ADR-003's `ContextBuilder` fix actually eliminated hallucination — becomes answerable for the first time. Generated tests can now be sampled and graded.
