---
kind: adr
id: ADR-114
title: ADR-114 — Retire purity.no_todo_placeholders and disable its remediation
status: accepted
---

<!-- path: .specs/decisions/ADR-114-retire-no-todo-placeholders.md -->

# ADR-114 — Retire `purity.no_todo_placeholders` and disable its remediation

**Status:** Accepted — governor-ratified 2026-06-18
**Date:** 2026-06-18
**Governing paper:** `.specs/papers/CORE-Rule-Authoring-Discipline.md`
**Retires:** the rule `purity.no_todo_placeholders` and its `fix.placeholders` auto-remediation routing.
**Grounding:** the Final Invariant ("never produce work it cannot defend"); the CORE honesty thesis (intent and findings are labelled by what can actually be defended).
**Prompted by:** the GRC catalog incident (2026-06-18) — the rule's remediation silently rewrote a correct sentence into a wrong one, which exposed that the rule had no recorded rationale and could not survive the conviction test.

---

## Context

`purity.no_todo_placeholders` says: *"Production code MUST NOT contain 'TODO', 'FIXME',
or 'TBD' strings; use the constitutional 'FUTURE' or 'PENDING' markers."* (authority: policy,
enforcement: **reporting**).

Examining it surfaced four problems and one reframe attempt that failed:

1. **No recorded rationale.** No `rationale` field, no originating ADR (`git log` traces it to
   a broad refactor commit). Its reason had to be reverse-engineered — a constitutional rule
   whose *why* is unrecorded is CORE failing its own thesis.

2. **It over-reaches onto the word-as-data.** The rule is a literal string-forbid (`\bTODO\b`)
   with no semantic discrimination: `# TODO: fix this` (the debt it means to catch) and
   `forbidden_patterns: ["\bTODO\b"]` (a GRC catalog *legitimately detecting placeholders in
   customer documents*) are the same string to it.

3. **Its remediation is actively harmful.** The `fix.placeholders` auto-remediation rewrote
   the GRC demo's prose — turning a correct sentence ("documents must be finalized — no TODO,
   TBD, FIXME text") into a wrong one ("…no FUTURE, pending, DRAFT, or PENDING text"). A
   reporting-only rule with a fixer that corrupts correct content is net-negative on its own.

4. **It inverts the honesty thesis.** A `TODO` is a developer being *honest*: "this part is
   incomplete." CORE's whole value is honesty about what it can and cannot defend; the Final
   Invariant is *served* by disclosing a gap, not by deleting the disclosure. Banning the
   marker does not complete the work — it pressures incompleteness to be **hidden** rather
   than flagged. The rule fights the constitution it lives in.

We tried to rescue the rule three times — ban → tracked-format `WORD(ref)` → delimited
`_WORD_(ref)` → back. Each reframe traded one defect for another (data over-reach vs. an
enforcement hole where bare untracked TODOs slip through vs. loss of standard tooling).
A rule that resists justification through three reframes, that neither author can defend with
conviction, in a **solo, continuously self-auditing, governor-reviewed** codebase where the
"abandoned ownerless debt" failure mode barely applies and genuine incompleteness is already
caught by CORE's deeper completeness, test-coverage, and defensibility mechanisms — does not
earn a place in the constitution.

## Decision

### D1 — Retire `purity.no_todo_placeholders`

Remove the rule from `.intent/rules/code/purity.json` and its enforcement mapping from
`.intent/enforcement/mappings/code/purity.yaml`. A `TODO`/`FIXME`/`TBD` in code is honest
signal that a part is incomplete; it is no longer a governed violation. Real incompleteness
remains governed by the mechanisms that actually assess it (completeness, `quality.*`,
test-coverage, the Final Invariant) — not by a string match on a note.

### D2 — Disable the corrupting remediation

Remove the `purity.no_todo_placeholders → fix.placeholders` routing from
`.intent/enforcement/remediation/auto_remediation.yaml`. With no rule mapped to it, the
`fix.placeholders` action is no longer dispatched — the prose-rewriting behavior is disabled.
This is the unambiguous-harm fix and stands on its own regardless of D1. Deleting the now-orphaned
`fix.placeholders` action/engine code is optional follow-up cleanup, out of scope here.

### D3 — Nothing mandatory replaces it; a visibility lens stays available as a future option

No new prohibition is introduced. If deferred work ever needs to be *visible* (e.g. a report:
"N deferred markers, M without a tracking reference"), the CORE-native form is a **reporting
visibility lens that surfaces, never suppresses** — honoring the honesty thesis. That is
explicitly **not** decided here; it is recorded as the opt-in shape should the need arise
(most likely if CORE gains contributors, where catching *others'* untracked debt has value
the solo case lacks).

### D4 — The corruption heals; the GRC catalog needs no special handling

With the rule gone, the GRC demo statement in `gap_analysis_service.py` is restored to its
correct wording as part of applying this ADR, and the NIST catalog's `\bTODO\b` detection
patterns and provenance prose are simply ordinary content — no carve-out, no exemption.

### D5 — This is the conviction test working, recorded as such

This ADR exists because an inherited, un-rationaled rule was put to the conviction test and
did not survive. Recording *why a rule was retired* is the same discipline as recording why a
rule is enacted: **no change to the constitution without a recorded reason.** This is a single
application of that principle, not a sweep — but it is a reminder that other un-rationaled
rules may warrant the same test.

## Consequences

- **A net-negative is removed:** a toothless (reporting), un-rationaled rule plus a fixer that
  corrupted correct content. No real coverage is lost — genuine incompleteness is caught by
  stronger mechanisms.
- **Honesty is restored at the marker level:** an inline "this is incomplete" note is no longer
  punished, so incompleteness gets flagged rather than hidden.
- **The governed rule count drops by one** (213 → 212). The retired rule lives in
  `rules/code/`, not the architecture set the CLAUDE.md digest counts, so the digest's
  `31/27/9 = 67` is unchanged by this ADR. (That digest already diverges from a fresh
  architecture count — pre-existing drift, surfaced rather than resolved here, per ".intent/
  wins: surface the divergence, don't resolve it in code.")
- **The remediation surface shrinks safely:** one ACTIVE routing removed; the
  remediation-honored invariant (`governance.remediation.*`) stays satisfied (fewer routings,
  all still honored).
- **The GRC catalog and demo are clean** without exemptions.

## Alternatives considered

- **Reframe to a tracked-deferral rule** (`WORD(ref, desc)`, standard or `_WORD_`-delimited).
  Rejected — three reframes each traded one defect for another, and the underlying value
  doesn't justify the maintenance in a solo, self-auditing codebase; the delimited form also
  created an enforcement hole (bare untracked TODOs slip through) and lost standard tooling.
- **Demote to advisory but keep the prohibition.** Rejected — a prohibition on honest
  incompleteness markers is the part that inverts the thesis; lowering its severity does not
  fix that.
- **Keep it as-is.** Rejected — no rationale, over-reaches onto data, and ships a corrupting
  fixer.
- **Build the visibility lens now.** Deferred (D3) — not needed for the solo case; recorded as
  the future shape.

## References

- `.intent/rules/code/purity.json` — `purity.no_todo_placeholders` (removed by D1).
- `.intent/enforcement/mappings/code/purity.yaml` — its mapping (removed by D1).
- `.intent/enforcement/remediation/auto_remediation.yaml` — `fix.placeholders` routing (removed by D2).
- `src/body/services/grc/gap_analysis_service.py` — the prose corrupted by the remediation; restored by D4.
- ADR-113 — sibling honesty work (per-finding evidence class); same thesis applied to findings.
- CLAUDE.md — constitutional-rule digest (unchanged; the retired code rule is not in the architecture set it counts).
