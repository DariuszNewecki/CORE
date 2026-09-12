---
kind: adr
id: ADR-160
title: 'ADR-160 — Risk classification as earned trust, and the authorization boundary'
status: accepted
depends_on: ["ADR-008", "ADR-159"]
---

<!-- path: .specs/decisions/ADR-160-risk-maturity-and-authorization-boundary.md -->

# ADR-160 — Risk classification as earned trust, and the authorization boundary

**Status:** Accepted — governor (D.Newecki), 2026-09-12.
**Date:** 2026-09-12
**Prompted by:** review of the direct (Proposal-bypassing) execution path surfaced while filing
#873's `GoalExecutionWorker` and while investigating ADR-159's D3 invalidation (see that ADR's
2026-09-12 Note). That review found the safe-auto-approval envelope does not bound the direct
execution path at all, and that several existing risk/approval surfaces in this codebase are
declarative rather than enforced.
**Relates:** ADR-008 (impact-level classification authority); ADR-059 D1 (the `RiskAssessment`
proposal-risk vocabulary); ADR-101 (commit authorship integrity — the same "who actually produced
this" discipline applied here to authorization rather than bytes); ADR-159 (the autonomy
acceptance boundary whose D3 invalidation this ADR is a direct consequence of).
**Supersedes:** nothing.

---

## Context

### The classification surface as it exists today

`.intent/enforcement/config/action_risk.yaml` classifies every atomic action into a closed,
three-value vocabulary — `safe | moderate | dangerous` — under ADR-008's authority
(`action_risk.yaml:17,25`). Exactly three actions currently carry `dangerous`:
`fix.settings_access`, `fix.vulture_heal`, `refactor.apply_split` (`action_risk.yaml:121-129`).

A second, differently-named vocabulary exists in parallel: `RiskAssessment`
(`src/will/autonomy/proposal.py:78`, docstring citing ADR-059 D1) classifies a Proposal's
`overall_risk` as `safe | moderate | high`. The two vocabularies are reconciled in the code
itself, not merely by convention — `_compute_flow_risk`'s own mapping (`proposal.py:209-217`)
states plainly that `"dangerous" and "high" name the same level in those two vocabularies`.
`requires_approval()` (`proposal.py:98-100`) returns true for both `moderate` and `high` — which,
once `dangerous` is read as this codebase's own name for `high`, means **`moderate` and
`dangerous` currently produce identical behavior**: the same approval requirement, no further
distinction between them.

### The direct path is not bound by the safe-auto-approval envelope

`validate_envelope()` (`src/will/autonomy/safe_auto_approval_envelope.py:54`) is called from
exactly one place: `ProposalStateManager.approve()` (`proposal_state_manager.py:279`) — a
Proposal-lifecycle gate. `ActionExecutor.execute()` (`src/body/atomic/executor.py`) never calls
it. The executor does read the same envelope's authorized-path-prefix list for an unrelated,
narrower purpose — denying a symlink that would escape an authorized prefix
(`executor.py:149-157`) — but its own docstring states plainly that a target outside every
authorized prefix "was never relying on this envelope... so this property has nothing to check
for it" (`executor.py:130-132`). The envelope bounds Proposals carrying a specific declared
`approval_authority`; it does not bound, and was never designed to bound, the direct
`ActionExecutor` path.

### Three declarative-only gates

Three further mechanisms exist in the codebase, read but not enforced:

- **The executor's dangerous-plus-write check** (`executor.py:506-551`, `_check_authorization()`)
  is a documented pass-through: *"Inline pass-through — authorization of record is the approval
  layer... This method intentionally returns `authorized: True`; it is NOT the authorization gate
  and never was."* Its own stated activation criterion: *"a dangerous action becoming reachable
  by a NON-governor caller — e.g. the action-execution surface exposed over the API, or
  non-governor CLI users. Until then the inline check is a pass-through by design"*
  (`executor.py:529-532`). It only logs (`executor.py:538-545`) and always returns
  `authorized: True` (`executor.py:547-551`).
- **`CommandExposure.GOVERNOR_ONLY`** (`src/shared/cli/command_meta.py:63`) is read only by an
  accessibility report (`src/cli/resources/admin/accessibility.py:77,94`); the `core_command`
  decorator that actually gates CLI execution never reads `.exposure`
  (`src/cli/utils/decorators.py:48,106,110`). `core-admin dev refactor` itself declares
  `exposure=CommandExposure.GOVERNOR_ONLY` (`src/cli/resources/dev/refactor.py:38`) — a
  self-declared label nothing checks at runtime.
- **`Worker.approval_required`** is read from the declaration into `self._approval_required`
  (`src/shared/workers/base.py:130-131`) and exposed as a read-only property
  (`base.py:429-431`). No code anywhere in `src/` reads `.approval_required` off a Worker
  instance. (A same-named but unrelated field, `Proposal.approval_required`, is live and
  load-bearing on a different class — `proposal.py:451`, set from `self.risk.requires_approval()`
  — the coincidence of names is itself worth flagging as a source of false confidence.)

### The direct path's actual bound is external to CORE

`develop_from_goal`'s only two current callers outside the CLI are both programmatic:
`POST /develop/goal` (`src/api/v1/development_routes.py:24-30`, router-level
`dependencies=[require_governor]`) and `StrategicAuditor.execute_approved_clusters`
(`src/will/agents/strategic_auditor/effects.py:146,176`), which calls it once a human governor
has cleared `Task.requires_approval` per cluster. Both gates are real, but both sit outside
CORE's own governance machinery, in the caller: `require_governor` authenticates the identity
making the HTTP request, not the scope of what the request will do once inside; clearing
`Task.requires_approval` is a boolean flip on an LLM-authored plan, not a scope-checked,
risk-classified artifact CORE can independently query afterward. #873's `GoalExecutionWorker`
(commit `706437a6`) makes the run this produces reconstructable from the blackboard; it does not
make it authorized in any sense CORE itself enforces. That gap is what this ADR addresses.

---

## Decisions

### D1 — Risk level is a maturity statement, not a property of an action

An action's classification in `action_risk.yaml` states what CORE has demonstrated it can do
safely at this point in its development — not how hazardous the operation is in the abstract.
Two actions with the same real-world blast radius may sit at different levels because CORE's
surrounding safety machinery (sandboxing, containment checks, test coverage, review discipline)
has matured further around one than the other. Levels are expected to move **down** over time as
that machinery improves, and this has already happened repeatedly during CORE's development
without being written down anywhere — the classification file's own git history is the only
record of decisions that were never recorded as decisions. That absence is unmarked intent inside
the enforcement configuration: the same class of defect ADR-159 D8 already names for the
repository's stopping rule, applied here to demotions instead.

### D2 — The three levels take three distinct behaviors

- **`safe`** — executes autonomously within the safe auto-approval envelope
  (`validate_envelope()`, Proposal-lifecycle only, per Context).
- **`moderate`** — requires Governor approval for each occurrence.
- **`dangerous`** — refused by default; runs only where the Governor has explicitly authorized
  that specific instance in advance.

This is a decision, not a description of the status quo: **`moderate` and `dangerous` are
behaviorally identical today** (Context, above), and the direct `ActionExecutor` path has no deny
for `dangerous` at all (`_check_authorization()` is a pass-through). D2 states what these three
levels must come to mean; it does not claim they mean it yet.

### D3 — Authorization gates on scope, not on caller

Any write whose targets were chosen by a planner rather than named by an authorized principal
must be represented as a Proposal before execution, regardless of which caller initiated the run.
A Governor-initiated CLI invocation authorizes the **goal**, not the plan derived from it —
`core-admin dev refactor` must not stamp `principal.governor` on the plan the goal produces. That
plan enters the ordinary safe-auto-approval route like any other, and escalates to the Governor
only where it leaves the envelope.

The reasoning: a bound supplied from outside CORE — "a human was at the keyboard" — is not a
property CORE can verify. It is true of `core-admin dev refactor` today only because a human
operator happens to type the goal text into a terminal CORE does not control and cannot inspect.
Nothing distinguishes that invocation, at the moment `develop_from_goal` receives it, from an API
call or a StrategicAuditor dispatch — all three hand the same function the same shape of input. A
gate that depends on which of three code paths called a function is not a gate; it is a
coincidence that has held so far. Scope — what the resulting plan actually touches — is the only
property CORE can check for itself, and is therefore the only property authorization may gate on.

### D4 — Demotion requires the Governor's signature

CORE may not lower its own risk classification under any evidence threshold, however strong.
CORE may assemble and present the evidence for a demotion — test coverage, incident history,
sandbox results, whatever a future risk-review capability gathers (D6) — but the Governor alone
signs it. Promotion to a stricter level needs no signature: CORE may raise its own caution level
unilaterally at any time, consistent with fail-closed discipline elsewhere in this codebase.

### D5 — Every level change is recorded with the level

A classification entry that changes must carry the reason, the date, the evidence relied on, and
the signing authority, stored so that a reader of the enforcement configuration can see why an
action sits where it does without reconstructing the decision from git blame and memory. The
storage format is not designed by this ADR — see Open items.

### D6 — A risk-review worker is anticipated, not authorized

The Governor expects that a dedicated worker will eventually track an action's demonstrated
safety over time and assemble the evidence a demotion under D4 would need. This ADR does not
authorize that worker. Nothing in this decision permits building it; it names the anticipated
shape only so a future proposal to build it is not treated as inventing a new category of thing.

---

## Open items

Recorded as open, not decided:

- The storage format for D5's classification-change record — a field on each `action_risk.yaml`
  entry, a separate governed log, or something else.
- The evidence bar a demotion must clear before the Governor will sign it.
- Whether `dev refactor --write` retains its current behavior in the interim before D3 is
  implemented.
- The sequencing of D3's implementation against ADR-159's remediation scope — its 2026-09-12 D3
  invalidation Note's item 2 (self-directed planning) is the capability whose output D3 here
  would eventually need to gate.

---

## Consequences

- No code, test, `.intent/` enforcement configuration, or risk classification changes as a result
  of this ADR. It is a decision record; D2 through D6 describe a target state the current
  codebase does not yet meet, stated in Context above without euphemism.
- Any future work implementing D3 changes `develop_from_goal`'s behavior for its two programmatic
  callers (`development_routes.py`, `StrategicAuditor`) — that is a separate, later action
  requiring its own scoping, not authorized by this ADR's acceptance.
- This ADR does not alter ADR-159's D1–D9 or its own 2026-09-12 D3 invalidation Note; it is a
  response to what that invalidation's remediation scope exposed, not a revision of it.

---

## Notes

<!-- Append-only. Amendments are added here, never by rewriting the decisions above. -->
