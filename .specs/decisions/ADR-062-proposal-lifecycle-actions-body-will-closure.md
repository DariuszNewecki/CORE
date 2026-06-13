---
kind: adr
id: ADR-062
title: ADR-062 — proposal_lifecycle_actions.py body→will closure
status: accepted
---

<!-- path: .specs/decisions/ADR-062-proposal-lifecycle-actions-body-will-closure.md -->

# ADR-062 — proposal_lifecycle_actions.py body→will closure

**Status:** Accepted
**Date:** 2026-05-19
**Authors:** Darek (Dariusz Newecki)
**Deadline:** 2026-09-16 (120 days)
**Closes:** First bullet of #313 (proposal_lifecycle_actions.py exclude)
**Relates to:** ADR-049 D3 (closure ADR + deadline requirement),
ADR-056 (Proposal domain governance), ADR-017 (claim.proposal atomic action),
CORE-Mind-Body-Will-Separation.md §5.4 Body→Will prohibition

---

## Context

`src/body/atomic/proposal_lifecycle_actions.py:25` imports
`will.autonomy.proposal.ProposalStatus` at module level:

```python
from will.autonomy.proposal import ProposalStatus
```

This violates `architecture.layers.no_body_to_will`
(`layer_separation.yaml` RULE 12) under the expanded bare-prefix
`forbidden:` list that landed in commit `6edec08d` (ADR-049 D1). The
exclude entry for this file was added alongside the rule expansion to
prevent a cliff-edge audit failure.

The import is required because:

- `claim.proposal` is an `@atomic_action`-registered Body action that
  promotes an approved Proposal into the `executing` lifecycle state
  (ADR-017). The action body inspects and asserts on `ProposalStatus`
  values to enforce the legal transition `approved → executing`.
- `ProposalStatus` is the canonical Proposal lifecycle enum and lives
  on the Proposal domain dataclass at
  `src/will/autonomy/proposal.py:33`. ADR-056 ratified the Proposal
  domain's residence in Will and the state-conditional invariants
  governed by `.intent/enforcement/contracts/Proposal.json`.
- The atomic action runs in Body because action dispatch and the
  `@atomic_action` registry are Body infrastructure — but the lifecycle
  vocabulary it operates over is Will-owned.

The architectural shape is correct (Body executes the transition; Will
defines the lifecycle); the layer import is the price of using the
Will-defined enum from Body.

---

## Why this is structurally harder than a one-line move

`ProposalStatus` is not a free-standing enum. It is referenced by:

- `Proposal.status` field on the Will-owned domain dataclass.
- `ProposalStateManager` (Will) — the runtime enforcer of state
  transitions per ADR-015 D2/D6.
- `.intent/META/enums.json` `proposal_status` vocabulary (governed by
  `vocabulary_canonical_store`).
- `.intent/enforcement/contracts/Proposal.json` `allOf`/`if`/`then`
  conditional blocks keyed on these values (ADR-056 D4).
- `autonomous_proposals.status` DB CHECK constraint values.

Moving the enum out of `will.autonomy.proposal` requires touching all
five surfaces in lockstep and re-validating the contract, the META
vocabulary, and the DB CHECK constraint values match. Doing it as part
of #313 closure would scope-creep the issue.

---

## Closure path

Two viable options for the eventual refactor:

**Option A — Move `ProposalStatus` to a shared lifecycle vocabulary module.**

Create `src/shared/lifecycles/proposal.py` containing only the
`ProposalStatus` enum (pure data, no Will dependencies). The Will
domain at `src/will/autonomy/proposal.py` re-exports it for backward
compatibility; the Body atomic action imports from `shared.*` and
crosses no layer boundary. This matches the
ADR-049 "contraction of `shared/` to pure contracts" long-horizon
direction (ADR-049 §Long-horizon direction): enums are contracts, not
logic.

**Option B — Pass `ProposalStatus` values into the atomic action as
plain strings, with validation handled at the Will boundary.**

The atomic action accepts a string status and delegates legality
checks to `ProposalStateManager.assert_legal_transition()` (a Will
method) via a Body service facade. The Body code holds no Will
reference; the Will code owns the enum.

Option A is preferred on first reading: it preserves type-safety in
Body and matches the precedent of `RiskAssessment`, `ProposalScope`,
`ProposalAction` (other Proposal-adjacent types already moved out of
Will into governed contracts under ADR-056 Wave 1). A definitive choice
between A and B is the work of the refactor itself, not this ADR.

---

## Deadline

**2026-09-16** (120 days from acceptance). This matches the deadline
horizon used by ADR-051 for the comparable
`file_handler.py` closure. The deadline triggers per ADR-049 D3:

- Warning state: audit emits a warning when this date passes if the
  exclude entry is still present.
- Blocking state: 30 days past deadline (2026-10-16), the entry is
  treated as a rule violation; `proposal_lifecycle_actions.py` fails
  audit until refactored or until this ADR is amended with a new
  deadline tied to a named blocker.

---

## Consequences

**Positive:**

- The body→will exclude has a named owner, a refactor path, and a
  deadline. The "TBD" deadline marker in `layer_separation.yaml` can
  be replaced with `2026-09-16` and a back-reference to this ADR.
- #313 closure is unblocked once all three body→will excludes have
  closure ADRs (ADR-062 / ADR-063 / ADR-064).
- The architectural question — "is `ProposalStatus` Will or Shared?"
  — is named explicitly rather than left implicit in an exempt import.

**Negative:**

- The refactor itself is not done; Body still imports from Will at
  module-load time. Until refactor, every consumer of
  `proposal_lifecycle_actions` carries the transitive Will import.

**Neutral:**

- The contract entry in `Proposal.json` already references
  `proposal_status` via the META enum (ADR-056), so the vocabulary
  store and the contract layer are already independent of Will-layer
  Python. Option A is therefore mechanically straightforward — the
  governance surface is ready; only the Python module location moves.

---

## Verification

This ADR is verified when, on or before 2026-09-16:

1. Either `src/body/atomic/proposal_lifecycle_actions.py:25` no longer
   imports from `will.*`, or this ADR has been amended with a new
   deadline and named blocker.
2. The `src/body/atomic/proposal_lifecycle_actions.py` entry in
   `architecture.layers.no_body_to_will` `excludes:` is removed (if
   refactored) or its comment is updated to reference this ADR's new
   deadline.

---

## References

- ADR-049 — Doctrine-rule parity; D3 sets the closure ADR + deadline
  requirement that this document satisfies.
- ADR-056 — Runtime data contracts; ratifies Proposal domain residence
  in Will and the governance shape that makes Option A tractable.
- ADR-017 — `claim.proposal` as atomic action; the action body that
  forces the Will import.
- ADR-051 — file_handler.py closure (precedent for this ADR's shape).
- `src/body/atomic/proposal_lifecycle_actions.py:25` — the import.
- `src/will/autonomy/proposal.py:33` — `ProposalStatus` definition site.
- `.intent/enforcement/mappings/architecture/layer_separation.yaml`
  RULE 12 `excludes:` block — the entry this ADR closes.
- `.intent/META/enums.json` `proposal_status` — vocabulary store
  governing the same value set.
