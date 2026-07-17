---
kind: adr
id: ADR-152
title: "ADR-152 — Generalizing governed_exclusions for ADR-049 D3's deadline-closure discipline"
status: accepted
---

<!-- path: .specs/decisions/ADR-152-exemption-schema.md -->

# ADR-152 — Generalizing `governed_exclusions` for ADR-049 D3's deadline-closure discipline

**Date:** 2026-07-17
**Governing paper:** none directly — implements ADR-049 D3
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-07-17 — drafted under governor direction, issue #794)
**Relates to:** ADR-042 D3 (the pre-existing register this ADR generalizes),
ADR-049 D3 (the decided-but-unbuilt deadline discipline this ADR wires up),
ADR-095 D3 (retired ADR-042's original modularity use case in favor of
`CORE_ROLE`, but explicitly kept the register's schema "in case it's needed
for non-`CORE_ROLE` carve-outs" — this ADR is that carve-out), #793
(worker-import exclude extraction — first migration candidate), #794 (this
ADR's originating issue), ADR-127 (D1–D3, D7 addendum — the "detect and
reclassify, don't just skip" philosophy this ADR's own Phase 2 extends)

---

## Context

### D3 was decided in May, never built

ADR-049 D3 (2026-05-15) requires every `excludes`-style entry across
`.intent/enforcement/mappings/**` to reference a closure ADR and carry a
deadline, enforced in two stages (warning past deadline, blocking 30 days
after). A grep of `src/` found no engine reading exclusion deadlines or
closure references — the discipline was decided and never wired up. The
2026-07-14 external review re-found the same gap D3 was written to close.

### The scope question resolved from ADR-049's own body

Issue #794 asked whether D3 was meant to bind every rule's `excludes`
mechanism, or only `architecture.shared.no_layer_imports` (the rule that
motivated it). ADR-049's own D1 table answers this directly — the
`no_body_to_will` row also invokes D3 for a *different* rule ("Add
`excludes:` for the 4 known violating files, each with a closure ADR per
D3"). D2 underwent the same broadening two days into the same document
(2026-05-27 amendment, CCC #463), from "import/layer papers" to "all
normative paper §s." D3 is general.

### The construct already existed — two days before D3 was written

Investigating #794's "first application" (`no_direct_worker_import`'s and
`no_layer_imports`'s excludes) surfaced that `scope.excludes` is used for
two unrelated purposes with no structural distinction: **definitional**
("this rule does not conceptually apply here" — test files, a layer
positively permitted to do what the rule forbids elsewhere; permanent, no
debt) and **amnesty** ("this file currently violates the rule; governance
temporarily permits it" — exactly what D3 is about).

The first draft of this ADR proposed a new `scope.exemptions` key to make
that split structural. Verifying that draft's design against the actual
schema and loader (rather than against argument alone) surfaced that the
split already exists, two days earlier: **ADR-042 D3 (2026-05-13)**
introduced `governed_exclusions` — a per-file exemption register, already a
top-level sibling to `scope` in `enforcement_mapping.schema.json`, already
schema-enforced (`additionalProperties: false`, a real `required` array),
and already wired into `rule_extractor.py`'s live exclusion pipeline
(`governed_exclusions[].file` is merged into the rule's active exclusion
set — the same mechanism `scope.excludes` uses). ADR-042 and ADR-049 reached
for the same kind of mechanism two days apart without referencing each
other. Building a third parallel construct would repeat that mistake rather
than fix it.

`governed_exclusions`'s original required fields (`file`, `class`,
`category` ∈ {facade, algorithm, catalog}, `rationale`,
`removal_condition`) are shaped for ADR-042's specific problem — a
class-size exemption that closes when an observable code *condition*
changes. They have no concept of a *deadline*. ADR-095 D3 (2026-06-06)
retired the register's original modularity use case in favor of in-file
`CORE_ROLE` declarations, but explicitly kept the register's schema "in
case it's needed for non-`CORE_ROLE` carve-outs" — this ADR is that
carve-out.

### Verified: zero live entries, small pre-existing schema drift

`governed_exclusions` currently has zero live entries anywhere in the
mapping tree (`code/modularity.yaml` holds an empty `governed_exclusions:
[]`, post-ADR-095 migration; a `vocabulary_registers.yaml` hit is a
comment). This ADR's day-one behavior is a clean pass, not a migration.

A dry-run of `enforcement_mapping.schema.json` against all 253 rule entries
across 57 mapping files found 5 pre-existing schema errors in 2 files — not
typos: `code/purity.yaml`'s `purity.logic_conservation` and
`data/governance.yaml`'s three `data.contracts.*` context-level checks
deliberately declare `scope.applies_to: []` (commented: *"Audit scope is
the empty set so periodic sensors skip the rule without removing it from
the registry (ADR-043 D7 / #310)"*), which the schema's blanket
`minItems: 1` never accounted for. Checked against `rule_extractor.py`: a
missing or empty `applies_to` already resolves to "match nothing" (the
loader's own fix for the historical #158 silent-widen-to-all-of-`src/`
bug) rather than the dangerous behavior `minItems: 1` was originally
guarding against — so relaxing it to `minItems: 0` does not reopen #158;
that fix lives at the loader, independent of the schema constraint.

### The document-routing path was ruled out, empirically

A second design draft proposed activating schema validation for mapping
files by adding `.intent/enforcement/mappings` to
`.intent/META/intent_tree.yaml`'s `validated_directories`. Tested directly
(added, ran `core-admin constitution validate`, reverted): this fails every
mapping file immediately with `'$schema' is a required property`.
`MetaValidator`'s directory-routed validation checks whole documents
against `GLOBAL-DOCUMENT-META-SCHEMA.json`, which requires a `$schema` key
and a `kind` from a closed 9-value enum (`rule_document`, `vocabulary`,
`worker`, `flow`, …) that has no `enforcement_mapping` member. Mapping
files also have no `$schema`/`kind` header at all, and are structurally a
*dict of many rule entries* (`mappings: {rule_id: {…}, …}`), not a single
document — a different validation architecture from what document-routing
assumes. Reconciling the two (headers on 57 files, a new `kind` enum value,
a per-file-not-per-entry schema) is real, separate work, named below (D6)
rather than attempted here.

---

## Decision

### D1 — Generalize `governed_exclusions` with a `closure_type` discriminator

No new schema key. `governed_exclusions` gains a `closure_type` field,
required, `enum: [condition, deadline]`:

- `closure_type: condition` — ADR-042's original shape. Requires `class`,
  `category`, `removal_condition`, as before. Closes when an observable
  code condition changes.
- `closure_type: deadline` — ADR-049 D3's shape. Requires `deadline`
  (ISO 8601 date), `closure_adr` (pattern `^ADR-[0-9]+$`), `tracking_issue`
  (pattern `^#[0-9]+$`). Closes on a named date backed by an accepted ADR.

`file` and `rationale` are required regardless of `closure_type`. A JSON
Schema `allOf`/`if`/`then` enforces both the positive requirement (the
right fields for the declared shape) and the negative one (an entry cannot
carry the other shape's fields — a `condition` entry smuggling in
`deadline`/`closure_adr`/`tracking_issue`, or vice versa, is rejected; this
was a real gap in the first draft of the discriminator, caught by
synthetic testing before it shipped).

A dedicated `closure_type` field was chosen over folding a fourth
`category: amnesty` value into the existing facade/algorithm/catalog enum
— `category` answers "what architectural role is this," a different
question from "how does this debt close," and overloading it would mix
two taxonomies in one enum.

### D2 — `scope.applies_to` may be empty for declared context-level checks

`minItems: 1` → `minItems: 0`, matching what the loader has already
guaranteed is safe (see Context) and what two existing rules already rely
on undetected. No behavior change to any currently-passing rule; closes
the only real drift the schema activation surfaced.

### D3 — Lifecycle, `closure_type: deadline` only

`closure_type: condition` entries have no deadline concept and are always
surfaced as acknowledged debt (below). For `closure_type: deadline`:

1. **Deadline not reached:** acknowledged, non-blocking governance-debt
   finding. Never silent — an exemption's existence is itself a finding.
2. **Deadline passed, closure ADR not accepted:** warning-stage finding.
3. **Deadline + 30 days passed, closure ADR still not accepted:** lapsed.
   (Phase 1 — see D6 — reports this; it does not yet stop the underlying
   rule from continuing to skip the file. See D7.)
4. **Deadline passed but the closure ADR *is* accepted:** treated as
   acknowledged debt, not escalated — an accepted closure lands the debt;
   it should not read as more urgent than a fresh exemption just because
   the calendar date has passed. Verified by test.
5. **Entry fails the schema** (missing a required field, or carries the
   wrong shape's fields): a distinct `malformed_entry` finding.

### D4 — New rule: `governance.exemption_debt.declared`, validating programmatically

A fifth check_type on the existing `TaxonomyGateEngine` (not a new engine
— `feedback_protocols_reflex_check`: an existing abstraction fits). Walks
every `.intent/enforcement/mappings/**/*.yaml`, and for every
`governed_exclusions` entry found:

- Loads `enforcement_mapping.schema.json` directly and validates the entry
  against `schema["properties"]["governed_exclusions"]["items"]`
  specifically — the sub-schema for one entry, not the whole mapping-entry
  schema (a rule's `engine`/`params`/`scope` are not part of a
  `governed_exclusions` item's shape).
- For structurally valid entries, computes the D3 stage and emits a
  finding carrying `context.stage`.

This validates the schema **programmatically inside the check**, not via
`MetaValidator`'s document-routing (ruled out above). It makes
`rule_extractor.py`'s existing comment — *"the additional fields are
documentation that constitution validate enforces"* — true for the first
time; today, nothing enforces it.

Severity is uniform per rule, not per finding (`rule_executor` overwrites
every finding from one rule to the rule's declared `enforcement` value).
This rule ships at **reporting** — every finding, whether malformed,
acknowledged, warning, or lapsed, currently surfaces at the same
(informational) severity, with `context.stage` carrying the real urgency
for a human reader. Stage-differentiated *blocking* behavior (a malformed
entry actually failing a commit) arrives when this rule promotes to
blocking wholesale, matching the standard reporting-to-blocking arc used
throughout this codebase — not something one reporting-posture rule can
express internally.

### D5 — Migration discipline: nothing migrates in this change

No automated migration of the 63 existing `excludes:` lists (31 files) —
each requires a human read to classify as definitional, amnesty, or
unclear; an automated pass would reproduce the same false positives
(`governance.mutation_surface.filehandler_required`'s exclusion of
`file_handler.py` reads amnesty-shaped in a keyword scan but is a
permanent structural self-reference — the file *is* the governed surface)
and false negatives (a list mixing both kinds, like
`logic_no_terminal_rendering`'s `src/cli/**` + `src/will/workflows/**` in
one block) a heuristic sweep produced during this investigation.

Two confirmed amnesty candidates surfaced: `no_direct_worker_import`'s 6
files (#793) and `logic_no_terminal_rendering`'s `src/will/workflows/**`
(previously untracked). Neither has a closure ADR today. Migrating either
into `governed_exclusions` with `closure_type: deadline` now would mean
inventing a governance document to satisfy this ADR's own schema —
circular. Each migrates once it has a real closure ADR; tracked against
#793 and a new issue for the channels case. A full manual classification
of the remaining ~61 lists is its own follow-on task, filed on acceptance,
not bundled here.

### D6 — Named, deferred: mapping files aren't schema-validated at all

This ADR's D4 works *around* the document-routing mismatch found while
verifying the `validated_directories` approach — it does not close it.
`.intent/enforcement/mappings/**` remains outside `MetaValidator`'s
directory-routed validation entirely; nothing but D4's narrow,
`governed_exclusions`-scoped check enforces any part of
`enforcement_mapping.schema.json` today. Reconciling the two validation
architectures (headers + a new `kind` enum value on 57 files, or a
dedicated per-file mapping validator that iterates `mappings:` entries
the way D4 does) is real, separate work — named here, per the same move
ADR-049 used for the `shared/` substrate contraction, so the next review
treats it as a marked trajectory, not a fresh finding.

### D7 — Phase 2, named direction, not built here: exemptions should be provably still necessary

`governed_exclusions[].file` is merged into the same skip-list
`scope.excludes` uses (D1's discovery, confirming suppression already
works) — but that also means the underlying rule is never re-evaluated
against an exempted file. A skip-list can assert an exemption is needed
once, at creation, and never again; it cannot detect that the violation
was fixed three commits later — the exact failure mode #788 (closed
`53bb182b`) found for `abandoned` blackboard findings, one governance-
artifact layer up, and the same principle ADR-127's clean-pass drain
already applies there.

The correct long-term shape: the owning engine (`ast_gate` first, since
both known amnesty candidates and #793's rule use it) evaluates the
exempted path anyway instead of skipping it; if the violation still
fires, reclassify as governed debt (D3 stage 1) rather than a blocking
finding; if it doesn't fire, the exemption is stale — a distinct finding,
not silence, since the path is provably no longer needed. This is real
per-engine work, materially larger than D1–D4, and not committed here. A
follow-on ADR (or a D8 amendment, append-only) authorizes it once a real
exemption exists to build it against.

---

## Consequences

### Positive

- D3's two-month-old decision has an engine behind it, closing #794,
  without introducing a second exemption construct alongside ADR-042's.
- `rule_extractor.py`'s "the schema validator is the canonical gate"
  comment is now true.
- The definitional/amnesty split is structural (`closure_type`), not
  comment-convention, going forward.
- The governor gains visibility into live governance debt via findings
  instead of a manual YAML grep — once real entries exist.
- Two real, separate gaps (D6's document-routing mismatch, D7's
  skip-vs-verify) are named on record rather than silently absorbed or
  rediscovered by the next review.

### Negative

- Phase 1 does not verify that a future exemption is *still* necessary —
  only D7 does, and it's deferred.
- The ~61 unreviewed `excludes:` lists may hide amnesty-shaped entries
  this ADR doesn't find. Bounded by the follow-on classification issue,
  not eliminated here.
- `#793`'s 6 files and the channels `workflows/**` exclude don't gain D3's
  deadline discipline until each has a closure ADR — the honest cost of
  not inventing one to satisfy this ADR's schema.
- Mapping files remain outside `MetaValidator`'s directory-routed
  validation entirely (D6) — this ADR's D4 is a narrow, working exception,
  not a general fix.

### Neutral

- No existing rule's enforcement behavior changes. `scope.excludes`
  continues to mean exactly what it always meant.
- `TaxonomyGateEngine` gains a fifth check_type; no new engine, no new
  worker, no database schema migration.
- `governance_pack.schema.json` (external/adoptable governance packs) is
  untouched — it never defined `governed_exclusions`, and this ADR is
  scoped to CORE's own internal mappings.

---

## Verification

Performed during drafting, not deferred to a future audit cycle:

- **Schema validity:** `enforcement_mapping.schema.json` parses as valid
  JSON; placed on disk and re-checked.
- **Zero drift:** all 253 live rule entries across 57 mapping files
  validate clean against the updated schema (was 5 errors / 2 files
  before D2's `minItems` fix).
- **Discriminator correctness (8 synthetic cases, all correct):** valid
  condition-closed entry passes; valid deadline-closed entry passes;
  deadline-closed missing `closure_adr` rejected; condition-closed missing
  `category` rejected; a `deadline`-typed entry carrying condition-shaped
  fields instead of deadline fields rejected; an entry with a genuinely
  unknown key rejected; a condition-closed entry smuggling in
  `deadline`/`closure_adr`/`tracking_issue` rejected; a deadline-closed
  entry smuggling in `class`/`category`/`removal_condition` rejected.
- **`validated_directories` activation ruled out empirically:** tested
  directly (added, ran `constitution validate`, reverted clean) —
  confirmed the document-routing mismatch in Context, not assumed.
- **D4 engine tests (9, all passing):** context-level dispatch is True;
  clean tree yields no findings; a malformed entry yields one
  `malformed_entry` finding; a condition-closed entry is always
  `acknowledged_debt`; a future-deadline entry is `acknowledged_debt`; a
  past-deadline entry with an unaccepted closure ADR is `warning`; a
  &gt;30-days-past-deadline entry with an unaccepted closure ADR is
  `lapsed`; a past-deadline entry with an *accepted* closure ADR stays
  `acknowledged_debt`, not escalated; unknown check_type returns the
  shared block marker.
- **Regression:** the two pre-existing `taxonomy_gate` test files (13
  tests) still pass unchanged.
- **Live check run:** `TaxonomyGateEngine.verify_context` against the real
  repo tree returns zero findings — matches the zero-live-entries claim.
- **`core-admin constitution validate`:** 9 errors before and after every
  change in this ADR, all pre-existing and unrelated (`artifact_types`,
  two `flow.*.yaml` files) — confirmed by diffing the error list, not
  just the count.
- **mypy / ruff:** clean on `taxonomy_gate.py` and both new test files.

---

## References

- ADR-042 D3 — the pre-existing `governed_exclusions` register this ADR
  generalizes, and the reason no new schema construct was needed.
- ADR-049 D1, D3 — the decided-but-unbuilt deadline-closure principle;
  D1's `no_body_to_will` row is the textual evidence resolving #794's
  scope question.
- ADR-095 D3 — retired `governed_exclusions`'s original modularity use
  case in favor of `CORE_ROLE`, explicitly kept the schema for
  non-`CORE_ROLE` carve-outs.
- #793 — worker-import exclude extraction; first migration candidate once
  it has a closure ADR.
- #794 — the issue this ADR resolves.
- ADR-127 (D1–D3, D7 addendum, `53bb182b`) — the "detect and reclassify,
  don't just skip" philosophy D7 above extends to `governed_exclusions`.
- Memory `feedback_protocols_reflex_check` — why this ADR extends
  `TaxonomyGateEngine` rather than introducing a new engine.
