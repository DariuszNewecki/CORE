---
kind: adr
id: ADR-026
title: ADR-026 — Validate `proposal.scope.files` non-emptiness at `Proposal.validate()`
status: accepted
---

# ADR-026 — Validate `proposal.scope.files` non-emptiness at `Proposal.validate()`

**Status:** Accepted
**Date:** 2026-05-05
**Governing paper:** `.specs/papers/CORE-Proposal.md`
**Author:** Darek (Dariusz Newecki)
**Closes:** #191
**Resolves:** ADR-021 D5 (the punted validation)
**Related:** ADR-021 (parent), ADR-014 (development-phase priority informs rejection semantics)

---

## Context

ADR-021 D5 explicitly punted validation that `proposal.scope.files` is non-empty. The ADR assumed every proposal reaching `ProposalExecutor.execute()` would carry a populated scope; if not, that was "a separate validation bug."

The 2026-05-05 investigation (issue #191) confirmed the assumption is unfilled. An empty-scope proposal currently:

1. Passes `Proposal.validate()` (which has five existing shape checks, none covering `scope.files`).
2. Is claimable with no collision (vacuous intersection of empty with anything).
3. Reaches the action-execution path.
4. **On the success branch:** `git_service.commit_paths(paths=[], ...)` raises `ValueError` per ADR-021 D1 design — late, loud, but uninformative about which proposal.
5. **On the failure branch:** `git_service.restore_paths(paths=[])` silently no-ops — a malformed proposal silently fails to roll back.

The hazard surfaces only at the very end of the success branch, with a generic `ValueError`. The earlier the rejection, the cleaner the diagnosis.

This ADR resolves the D5 punt.

---

## Decision

A sixth check in `Proposal.validate()`:

```python
# 6. Must declare at least one file in scope (issue #191).
if not self.scope.files:
    errors.append("Proposal must declare at least one file in scope.files")
```

This represents three coordinated choices:

1. **Site:** `Proposal.validate()`. The proposal is the unit being validated; five existing shape checks already live there.
2. **Rejection semantics:** validation error returned to caller. Matches the existing pattern; three workers (`proposal_worker`, `test_remediator`, `violation_remediator`) already handle validation errors from this surface.
3. **Scope of "non-empty":** `scope.files` specifically. That is what `commit_paths` consumes; that is what fails when the field is empty.

---

## Alternatives Considered

### Sites

- **`ProposalScope.__post_init__`** — earliest possible rejection. Rejected: couples validation to dataclass construction; `ProposalScope` may be reused in non-file contexts; over-broad.
- **`ProposalScope.validate()` (new method)** — colocated with the type. Rejected: redundant with `Proposal.validate()`; adds a second validation surface to maintain for marginal benefit.
- **`ProposalRepository.create()` (persistence boundary)** — would close the broader bypass (any caller of `create()` that skipped `Proposal.validate()` would still be checked). Rejected as primary: changes who validates what at the persistence boundary; warrants its own ADR. Not precluded as a future addition (see Non-Goals).
- **`ProposalExecutor.execute()` pre-flight** — most defensive against the actual failure mode. Rejected as primary: catches too late — the proposal has been claimed and the AtomicAction may have run. Acceptable as defensive fallback if the primary check is bypassed; the existing `commit_paths` ValueError already plays this role.

### Rejection semantics

- **`ValueError` at construction** — refuse to construct a malformed proposal. Rejected: loses the validation surface entirely; a buggy worker producing empty-scope proposals would crash at construction with no validation-error trail.
- **Persist + mark failed in `core.autonomous_proposals`** — record the rejection in the proposals table; plays well with §7a revival. Rejected: dilutes the proposals table with malformed entries. Forensic trace is achievable via the existing validation-error logging in workers; persisting malformed records to satisfy that need is the wrong tool.
- **Belt-and-suspenders** — refuse at construction *plus* persisted-failure for legacy paths. Rejected: overkill for a single-field check; two enforcement layers to maintain when one is sufficient.

### Scope coverage

- **At least one of `files`/`modules`/`symbols`/`policies`** — broader rule allowing for future executable-without-files proposal kinds. Rejected as premature: no such proposal kind currently exists. If one is introduced, broadening becomes a deliberate decision with this ADR as precedent.

---

## Consequences

**Positive:**

- Empty-scope proposals are rejected at the earliest point that has full proposal context.
- The `commit_paths(paths=[])` ValueError on the success branch becomes unreachable for validated proposals; the malformed-proposal silent no-op on the failure branch becomes unreachable for the same reason.
- The validation surface is honest: a proposal that passes `Proposal.validate()` is structurally executable.
- Defense-in-depth is preserved — `commit_paths` remains the backstop if `Proposal.validate()` is ever bypassed (see negatives).
- Forensic trace for rejected proposals uses the existing validation-error logging in workers; no new mechanism.

**Negative:**

- The check sits at the proposal layer, not the persistence boundary. A future code path that writes proposals directly to `core.autonomous_proposals` without calling `Proposal.validate()` would bypass this check. The current `commit_paths` ValueError catches such proposals at execution, but later than the proposal layer would. Closing this gap is a separate ADR question (see Non-Goals).
- Future executable-without-files proposal kinds will trigger a broadening decision. The narrow rule is deliberate; broadening is not free.

---

## Non-Goals

- **Validation at the persistence boundary.** Whether `ProposalRepository.create()` should re-validate every proposal (Site 4 in the #191 investigation) is a separate architectural question. It changes who validates what at the persistence boundary and warrants its own ADR. This ADR's choice of Site 3 does not preclude that future ADR; it leaves the persistence boundary trusting its callers for now.
- **Broader scope coverage.** Whether the rule should require at least one of `files`/`modules`/`symbols`/`policies` is deferred. No executable-without-files proposal kind currently exists. If one is introduced, this ADR becomes the explicit precedent for the broadening decision: the current narrow rule is deliberate, not accidental.

---

## References

- Closes: #191 (Validate proposal.scope.files non-emptiness at proposal creation).
- Investigation comment: https://github.com/DariuszNewecki/CORE/issues/191#issuecomment-4380727235.
- Implementation commit: 62a1ab5f.
- Resolves: ADR-021 D5 punt.
