---
kind: adr
id: ADR-051
title: ADR-051 — file_handler.py shared/ excludes closure
status: superseded
---

<!-- path: .specs/decisions/ADR-051-file-handler-shared-excludes-closure.md -->

# ADR-051 — file_handler.py shared/ excludes closure

**Status:** Accepted
**Date:** 2026-05-15
**Governing paper:** `.specs/papers/CORE-Capability-Scoped-Filesystem-Authority.md`
**Authors:** Darek (Dariusz Newecki)
**Deadline:** 2026-09-12 (120 days)
**Closes:** Final bullet of #315 (Tier B/1)
**Relates to:** ADR-049 D3 (closure ADR + deadline requirement),
#157 (api/main.py composition-root exemption — same architectural
shape, parked), CORE-Mind-Body-Will-Separation.md §7.2 Admission
Test 1

---

## Context

`src/shared/infrastructure/storage/file_handler.py` imports from two
layers it must not, per `architecture.shared.no_layer_imports`
(layer_separation.yaml RULE 15):

- `body.governance.intent_guard.get_intent_guard` — used in `__init__`
  to construct `self._guard`, which `_guard_paths` invokes for every
  write to validate the transaction.
- `mind.governance.violation_report.ConstitutionalViolationError` —
  raised in `_guard_paths` when `IntentGuard.check_transaction` returns
  a rejection. The exception is a `ValueError` subclass carrying the
  structured `list[ViolationReport]` for downstream persistence.

The other five entries in the rule's `excludes:` list were resolved
in the same session that filed this ADR:

- `refusal_repository.py`, `decision_trace_repository.py` (dead shims,
  closes #314, commit `ad206f50`)
- `service_registry.py`, `bootstrap_registry.py`, `workers/base.py`
  (stale entries — never matched real violations; #315 Phase 1,
  commit `70117660`)
- `vector/cognitive_adapter.py` (swapped TYPE_CHECKING import for
  existing `CognitiveProtocol`; #315 Tier B/3, commit `e5ad89f1`)
- `context/service.py` (new `BrainServicesProvider` protocol injected;
  #315 Tier B/2, commit `c9332d73`)

`file_handler.py` remains. ADR-049's own Negative-consequences section
named this file explicitly as "not a one-line move."

### Why this is structurally harder than the prior four

- **Call surface.** 27 instantiation sites of `FileHandler(repo_path)`,
  all passing a single positional `str`. CLI (6), Body (14), Shared
  (3), tests (4). None inject a guard or are positioned to.
- **`IntentGuard` is rich.** Module-level singleton; loads constitutional
  rules from the Mind; enforces a 3-tier model (hard-invariant
  on `.intent/`, constitutional, policy). Extracting a faithful protocol
  is non-trivial.
- **`ConstitutionalViolationError` is tightly coupled to its payload
  `ViolationReport`.** Both live in `mind/governance/violation_report.py`.
  Relocating only the exception splits the pair; relocating both moves
  a chunk of mind governance into shared.
- **FileHandler is the canonical write gate.** CLAUDE.md mandates that
  all file mutations route through it. Making the guard optional — so
  27 callers can default to `None` — converts FileHandler into an
  unsupervised raw-write path and defeats the design.

### Architectural framing

The arrangement may be structurally correct as-is. FileHandler is the
composition root for repository writes — analogous to how `api/main.py`
is the composition root for app startup (#157). Composition roots, by
their nature, wire layers together; the "no shared→body" admission
test may need to recognize them as a sanctioned exemption category
rather than as ordinary shared/ files. This question is unresolved
across both #157 and this ADR; ADR-051 does not pre-judge it.

---

## Decision

Defer the structural resolution. By the deadline below, the file
must be removed from the excludes list via one of two paths, each
of which would carry its own successor ADR:

**Path X — Composition-root exemption.** Sanction FileHandler as a
named composition-root file (matching the framing being explored
for `api/main.py` under #157). Annotate the excludes entry with a
clear "composition root — sanctioned exemption" justification.
Update `CORE-Mind-Body-Will-Separation.md` §7.2 Admission Test 1 to
recognize "composition root" as an exemption category. This closes
both ADR-051 and #157 with the same framing.

**Path Y — Extract `MutationGuardProtocol` + relocate
`ConstitutionalViolationError`.** Define a minimal protocol in
`shared/protocols/` (single `check_transaction` method). Relocate
`ConstitutionalViolationError` (and possibly `ViolationReport`) to
`shared/exceptions/` or `shared/models/`, with re-export shims in
`mind/governance/` for backward compatibility during migration. Add
an optional `guard: MutationGuardProtocol | None = None` constructor
parameter to FileHandler. Update the 27 callsites in batches to inject
a guard (most can pass `service_registry.get_intent_guard()`; tests
pass a permissive no-op). Once all callsites inject explicitly, make
the parameter required and remove the body/mind imports. Estimated
2–3 sessions of focused work.

The choice between Path X and Path Y is itself a decision that warrants
its own ADR — it ratifies (Path X) or rejects (Path Y) "composition
root" as a sustainable exemption category in CORE. ADR-051 records
the deferral and the deadline; the successor ADR records the choice.

### Until resolution

The excludes entry remains, annotated with this ADR's reference. The
annotation replaces the current "TEMPORARY — violations pending
remediation" comment for this line:

```yaml
# file_handler.py: imports body.governance.intent_guard +
#   mind.governance.violation_report.ConstitutionalViolationError —
#   closure deferred per ADR-051, deadline 2026-09-12.
- "src/shared/infrastructure/storage/file_handler.py"
```

(The YAML edit is governor-applied; not part of this ADR's acceptance.)

---

## Consequences

### Positive

- **Final #315 bullet is closed under ADR-049 D3.** An accepted
  closure ADR with a deadline satisfies the rule even though the
  excludes entry physically remains. The pattern matches what
  ADR-049 D3 was designed to formalize.
- **Architectural decision is named and time-boxed.** The
  composition-root question becomes a tracked decision with a
  deadline rather than rotting on a parking lot.
- **Defers a meaningful choice until it is worth making.** "Compose
  or extract" is genuinely contested. Forcing the answer in a single
  session would have produced either a hasty refactor (Path Y on
  inadequate analysis) or a hasty exemption (Path X without paper
  amendment). Both are worse than the deferred-with-deadline shape.

### Negative

- **The debt is not removed; it is parked with a deadline.** Two of
  the three Tier B refactors in this session were full removals;
  this one is not. The pattern of "refactor-out wherever possible"
  bends here.
- **The same architectural question remains parked under #157.**
  ADR-051 does not unblock #157 — they remain independently parked
  until the composition-root question is settled by the successor
  ADR.
- **120 days is a soft commitment.** ADR-049 D3 specifies a 30-day
  grace period after the deadline before the entry is treated as a
  rule violation. If no successor ADR is filed by 2026-10-12, the
  audit will start failing on file_handler.py — a hard forcing
  function, but one that requires governor attention to head off.

---

## Verification

This ADR is verified when:

1. ADR-051 is marked Accepted in `.specs/decisions/`.
2. The excludes entry in `layer_separation.yaml` carries the ADR-051
   reference comment.
3. #315 is closed with reference to this ADR (the rule's excludes
   list is "closed" per ADR-049 §"Verification" point 1: each entry
   either refactored or backed by an accepted closure ADR).

The successor ADR (Path X or Path Y) is filed by the deadline
2026-09-12.

---

## References

- ADR-049 D3 — closure ADR + deadline requirement
- ADR-049 §"Negative consequences" — names file_handler.py as
  "not a one-line move"
- #157 — api/main.py composition-root exemption (same architectural
  shape, parked)
- #315 — shared/ excludes closure epic; this ADR closes the final
  bullet
- CORE-Mind-Body-Will-Separation.md §7.2 Admission Test 1 — the
  shared-layer admission test that file_handler.py would need to
  be re-evaluated against under Path X
- Commits closing the other five #315 bullets: `ad206f50` (#314),
  `70117660`, `e5ad89f1`, `c9332d73`
- CLAUDE.md "All file mutations go through FileHandler" — the
  invariant that makes "make the guard optional" a non-viable
  resolution path

---

## Note — 2026-06-26: Superseded by ADR-126

A 2026-06-26 investigation against the live codebase found that Path X and
Path Y both accepted the wrong premise — that FileHandler belongs in Shared.
The investigation identified:

- `shadow_materializer.py` already uses the correct DI pattern (TYPE_CHECKING
  import + injected parameter) and is not a violation.
- `serializers.py` and `test_runner.py` are operational service code that
  escaped Shared's substrate contract; they pulled FileHandler into Shared,
  not the other way around.
- FileHandler is a governance-enforcement write gate — an execution-tier
  concern that belongs in `body/infrastructure/storage/`.

ADR-126 supersedes this ADR with a staged migration: DI injection into the two
Shared instantiators (Stage 1), followed by the physical move of FileHandler to
Body (Stage 2), followed by caller import-path cleanup (Stage 3). The 2026-09-12
deadline is inherited unchanged.

The Path X / Path Y framing in this ADR's Decision section is superseded;
ADR-126 is the governing document for the file_handler.py closure.
