---
kind: adr
id: ADR-105
title: 'ADR-105 — Document model for `.specs/`: typed headers, forked vocabulary'
status: accepted
---

<!-- path: .specs/decisions/ADR-105-specs-document-model.md -->

# ADR-105 — Document model for `.specs/`: typed headers, forked vocabulary

**Date:** 2026-06-13
**Governing paper:** `.specs/papers/CORE-Specification-as-Source.md`
**Status:** Accepted (governor decision 2026-06-13 — the distinction (operational vs documentary lifecycle) and all decisions D1–D8 stand; D3 Option B (`doctrine_tier`, not reused `authority`) ratified for the stated reasons (non-identical sets + token collision); D7 confirmed as YAML frontmatter (not flipped to the prose-convention fallback). Implementation lands as one change-set per the Consequences section; `.intent/META/enums.json` is constitutional core and is surfaced for the heightened-confirmation gate before writing.)
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-13 — drafted under explicit "lets implement it" authorization after a recon thread that established the gap from source: `.intent/META/`, `enums.json`, `GLOBAL-DOCUMENT-META-SCHEMA.json`, and the `spec_markdown` artifact type were read directly; the free-text `**Status:**` distribution across `.specs/papers/` was counted, not recalled. The governor pre-selected the forked-vocabulary direction — Option B, a distinct `doctrine_tier` rather than a reused `authority` — on the grounds that the sets are not identical and the shared token is itself a drift vector.)

**Grounding decisions:**
- ADR-090 D2/D7 — the artifact-type registry as the published contract for "what classes of file CORE governs"; `crawl_scopes.yaml` retirement folded discovery into per-type `discovery` globs. This ADR splits the single `spec_markdown` declaration that ADR-090 D7 created into per-class types, and lifts each from `schema_ref: null` to a real header model.
- ADR-049 D2 / Governance-Topology row 2 — every accepted ADR cites a grounding paper (or supersedes a predecessor). This ADR turns that obligation from prose into a typed `grounding` header field, which is what makes it mechanically checkable (closes the backlog tracked at #473).
- ADR-073 D6/D10 — the CCC's ROW3_CITATION check and the `normative_markers.yaml` closed register. Precedent that `.specs/` is already a machine-read coherence surface with a governed vocabulary for *what a paper claims*; this ADR adds the missing governed vocabulary for *what state a paper is in*.
- ADR-056 #366 — the `enums.json` discipline: every closed lifecycle vocabulary lives in the central store, `$ref`-ed by canonical pointer, with subset enums for narrowed contexts. The new `.specs/` enums follow this exact pattern.

**Related:**
- #627 — foundational papers carry `Status: Draft (Greenfield)` while cited as authority by Accepted ADRs/papers. The instance that surfaced the gap (F-04 false-positive, one wasted review session). This ADR makes that contradiction a firing CCC check rather than a prose smell.
- #616 — "ADR status taxonomy: split governor-approval from coherence-verification." Same root cause from the ADR side: `Status:` is overloaded. The two-axis model here (status × doctrine_tier) is the structural answer; #616's approval/coherence split can sit on top of the `adr_status` enum.
- #473 — 52 accepted ADRs missing a grounding citation. Closed structurally by the typed `grounding` field (D5) plus the CCC check (D6).
- #469 — 352 paper §s owe an enforcing-rule citation or aspirational marker. Already a CCC ROW3 check; this ADR anchors it to the typed header so the per-§ obligation reads against a declared document status.
- `.intent/META/GLOBAL-DOCUMENT-META-SCHEMA.json` — the `.intent/`-side precedent this ADR deliberately does *not* reuse verbatim (see D2/D7).
- `.intent/artifact_types/spec_markdown.yaml` — the single undifferentiated declaration D4 replaces.
- Memory `[[feedback_two_surface_requires_two_structures]]` — when a unification does not survive material differences, the unification was the bug. The operational and documentary lifecycles are two surfaces; D2 keeps them two structures.
- Memory `[[feedback_enum_subset_canonicalize_and_fail_closed]]` — the superset + per-class subset shape used in D5.
- Memory `[[feedback_half_built_schema_pattern]]` — the empty `.specs/META/` and `.specs/contracts/` directories are exactly this: scaffolding for a model that was never built.

---

## Context

### The gap

`.intent/` documents are fully modeled. A closed `kind` enum (9 data-artifact kinds) is enforced by per-kind META schemas under `.intent/META/`, sitting under `GLOBAL-DOCUMENT-META-SCHEMA.json`, which requires every non-META `.intent/` document to declare `$schema` + `kind` and, where `metadata` is present, `id / title / version / authority / status` — with the `authority` and `status` *enums* delegated to the per-kind schema and sourced from the central `enums.json` store.

`.specs/` documents have none of this. The 105 ADRs, 76 papers, 6 requirements, 5 planning docs, charter, and northstar all collapse into a **single artifact type** — `spec_markdown` — declared with `identity_key: path`, `schema_ref: null`, `change_record: text_diff`. There is no `kind`, no required header, no closed `status`, no tier vocabulary. `.specs/META/` and `.specs/contracts/` exist as **empty directories**.

The visible symptom: the `**Status:**` line on `.specs/` documents is free text. Across `.specs/papers/` alone it carries ~15 distinct values — `Canonical` (37), `Draft (Greenfield)` (8), `Constitutional Semantics Paper`, `Constitutional Paper`, `Constitutional Companion Paper`, `Authoritative`, `Architectural Vision (Exploratory)`, and a long tail of one-offs — with no document defining what any of them mean or how they rank.

### Why this is the same gap four times

The cost is not hypothetical and not isolated. A 2026-06-10 external governance review produced a Critical-severity false positive (#627) because a load-bearing doctrine paper read as `Draft` "not in force." The ADR `Status:` field is acknowledged-overloaded (#616). 52 ADRs cannot be mechanically verified as grounded because `grounding` is prose, not a field (#473). 352 paper §s owe a citation against an undeclared document status (#469). All four are one missing thing: **`.specs/` has per-class documents but no per-class document models.**

### The distinction this ADR vocalizes

The distinction between `.intent/` and `.specs/` is stated at the corpus level (CLAUDE.md: "`.intent/` is law read by the runtime; `.specs/` is architectural reasoning read by humans"; the `spec_markdown` vs `intent_yaml` artifact-type descriptions; the GLOBAL schema scoping itself to `.intent/`). It has **never been vocalized at the metadata-semantics level**, and that omission is why attribute reuse looks free when it is not:

- `.intent/` metadata describes an **operational / enforcement** lifecycle — *is this law loaded and in force* (`status: draft|active|deprecated`), *at what enforcement layer does it act* (`authority: meta|constitution|policy|code`). Runtime-consumed.
- `.specs/` metadata describes a **documentary / epistemic** lifecycle — *is this reasoning accepted, is it the canonical record, has it been superseded.* An ADR is never "active/deprecated"; it is "proposed/accepted/superseded." Human- and CCC-consumed.

These are different *kinds* of lifecycle, not one lifecycle in different words. The sharpest trap is the token **`authority`**: in `.intent/` it means *enforcement layer*; a `.specs/` document enforces nothing, so its "authority" is *doctrinal binding weight*. Reusing the word across two meanings is the precise hidden-convention shift the corpus exists to prevent.

---

## Decisions

### D1 — `.specs/` documents carry a typed, validated header (constitutional)

Every `.specs/` document declares machine-readable header metadata, validated at load against a per-class schema, with all closed vocabularies sourced from a central store and **failing closed** on an unknown or missing value. The *modeling mechanism* of `.intent/` is reused wholesale: header contract + central `enums.json` + `$ref` + fail-closed validation. What is **not** reused is any vocabulary whose meaning is operational.

### D2 — The vocabulary is `.specs/`-specific, not inherited

Because `.specs/` models a documentary lifecycle, its enums are distinct from `.intent/`'s operational ones. In particular, `.specs/` document status is **not** `draft|active|deprecated`. Inheriting the operational vocabulary would conflate the two surfaces (`[[feedback_two_surface_requires_two_structures]]`).

### D3 — The tier axis is `doctrine_tier`, a distinct enum — not a reused `authority` (Option B)

The doctrinal-weight axis is a new enum named `doctrine_tier`, **not** the `.intent/` `authority` enum:

```
doctrine_tier: constitution | foundational | informational
```

Two reasons, both decisive: (1) the sets are not identical — `.specs/` needs `informational` (which `.intent/` has no use for) and does not use `code` (papers are not code-tier); (2) reusing the *token* `authority` for two different meanings is itself a drift vector, and a distinct name costs one word now to prevent a silent semantic collision later.

### D4 — Per-class artifact types replace the `spec_markdown` blob

The single `spec_markdown` artifact type is replaced by per-class declarations, each with a precise `discovery` glob and a **non-null `schema_ref`**:

| `id` | discovery |
|---|---|
| `adr` | `.specs/decisions/ADR-*.md` |
| `paper` | `.specs/papers/CORE-*.md` |
| `requirement` | `.specs/requirements/*.md` |
| `planning` | `.specs/planning/*.md` |
| `charter` | `.specs/CORE-CHARTER.md` |
| `northstar` | `.specs/northstar/*.md` |

Crawl/vector routing (`vector_collection: core-specs`), `identity_key`, and sensor/action wiring carry forward from the retired `spec_markdown` declaration unchanged.

### D5 — The closed enums and relation fields (new in `enums.json`)

Following the `enums.json` superset + per-class-subset pattern:

- `document_kind` — `adr | paper | requirement | planning | charter | northstar`.
- `document_status` (superset) — `draft | proposed | accepted | canonical | superseded | retired`, with per-class subsets:
  - `adr_status` — `proposed | accepted | superseded | retired`
  - `paper_status` — `draft | canonical | superseded | retired`
  (Requirements/planning subsets defined when those classes are modeled; D8.)
- `doctrine_tier` — per D3.
- Typed relation fields on the header: `supersedes` (doc id or null), `depends_on` (list of doc ids), `grounding` (list of grounding-paper ids; the ADR-049 D2 obligation as a field).

### D6 — Validation lands in two hooks that already exist

1. **Load-time:** each per-class artifact type's `schema_ref` points at its header schema; the header is schema-validated at load, failing closed.
2. **Coherence-time (CCC):** a new check makes status-vs-corpus drift fire instead of smell — *a document cited as authority by an `accepted`/`canonical` artifact may not itself be `draft`* (the #627 contradiction), and *an `accepted` ADR must declare `grounding` or `supersedes`* (the #473 obligation).

### D7 — Header representation: YAML frontmatter (entailed by D1; flagged for ratification)

"Reuse the mechanism" (D1) means JSON-schema validation, which requires a *structured* header block — i.e. YAML frontmatter at the top of each document. A `**Status:**` prose line would require authoring a *new* parser, which is not reuse. Therefore `.specs/` documents gain a YAML frontmatter block carrying the D5 fields; the human-readable prose body is untouched. Migration adds a frontmatter block to ~181 documents — mechanical and scriptable, no prose rewrite.

This is the one sub-decision not separately pre-selected by the governor; it is recorded here as the choice **entailed** by D1 and surfaced explicitly for ratification. If the governor prefers to avoid the 181-file migration, the fallback is a CCC value-validator over the existing `**Field:**` convention — smaller migration, but a bespoke parser rather than reuse of the schema machinery.

### D8 — What this ADR does NOT decide

- The per-class **required-sections** contract (e.g. "an ADR must have Context / Decisions / Consequences"). The CCC already does partial required-section checks; formalizing the full per-class section contract is separate scope.
- **BYOR** consumers' own `.specs/`-shaped document classes. The artifact-type registry already supports their adding declarations; this ADR models CORE's own classes only.
- Whether to **generalize** `GLOBAL-DOCUMENT-META-SCHEMA.json` to span both trees or author a **sibling** `.specs/`-global schema. Recommendation: a sibling, to keep the operational/documentary boundary clean at the schema layer too — but the choice is deferred to implementation.
- Requirements/planning **status subsets** beyond ADR and paper (defined when those classes are migrated).

### D9 — `adr_status` tracks governor-approval only; CCC-verification is a separate axis

`adr_status: accepted` answers one question: **has the governor ratified this decision?**
It does not encode coherence-verification, implementation completeness, or CCC state.

The CCC's coherence checks (ROW2_GROUNDING, ROW3_CITATION, etc.) run independently and
may emit findings against `accepted` ADRs. This is normal and expected: a finding against
an accepted ADR records implementation coherence debt, not a challenge to the acceptance
itself. An ADR remains `accepted` regardless of open CCC findings; findings are resolved
through the triage process, not by reverting the acceptance status.

Operationally the two axes are tracked separately and do not drive each other:

| Axis | Tracked by | Lifecycle |
|------|-----------|-----------|
| Governor-approval | `adr_status` header field | proposed → accepted → superseded / retired |
| Coherence-verification | CCC engine (database) | candidates → reviewed → dismissed / confirmed |

This is the two-axis split raised in **#616**. The answer is: `adr_status` is the
governance-decision axis and is intentionally narrow. CCC state is the coherence axis and
is intentionally independent. Neither replaces the other.

---

## Ratifications (governor — 2026-06-13)

1. **D1–D2 (reuse mechanism, fork vocabulary)** — ratified. `.specs/` documents carry typed, fail-closed headers; the vocabulary is `.specs/`-specific, not the operational `.intent/` enums.
2. **D3 (`doctrine_tier`, Option B)** — ratified explicitly. The sets are not identical (`.specs/` needs `informational`, does not use `code`) and reusing the `authority` token across two meanings is a drift vector.
3. **D4–D6 (per-class artifact types, enums + relation fields, two-hook validation)** — ratified.
4. **D7 (header representation)** — confirmed as **YAML frontmatter**; the prose-convention fallback was not selected.
5. **D8 (deferred scope)** — accepted as the boundary of this change-set: requirements/planning status subsets and the GLOBAL-schema generalize-vs-sibling choice land later.
6. **D9 (governor-approval vs CCC-verification split)** — closes #616. `adr_status` is the governance-decision axis only; CCC findings against accepted ADRs are normal implementation-coherence debt, not acceptance-validity challenges. The two axes are tracked separately and do not drive each other.
7. **Consequences** — implement as one change-set and close #627, #616, #473, #469 against this ADR; do not file new issues. `.intent/META/enums.json` (constitutional core) is surfaced for the named heightened-confirmation gate before writing.

---

## Consequences

### What this absorbs

On acceptance + implementation, this framework retires four open issues rather than spawning new ones: **#627** (status drift → D6 CCC check), **#616** (status taxonomy → D5 two-axis enums), **#473** (ungrounded ADRs → D5 typed `grounding` + D6 check), **#469** (uncited §s → anchored to declared status). Each closes against this ADR, not a separate fix.

### The classification question becomes derivable

The recurring "can the 10 Draft-Greenfield papers be classified correctly?" question was unanswerable because no model declared the classes or their lifecycles. Once D5 exists, classification is largely **derivable** from the citation graph: a paper cited as doctrine by an `accepted` ADR is `doctrine_tier: foundational` (or `constitution`), `paper_status: canonical`. The migration script can propose the per-document assignment; the governor ratifies the residue.

### Migration shape

One change-set after acceptance: (1) add the enums to `enums.json`; (2) author the per-class header schemas under `.specs/META/`; (3) replace `spec_markdown` with the D4 per-class artifact types; (4) add the D6 CCC check; (5) backfill frontmatter across ~181 documents (scripted; classification proposed, governor-ratified). Steps 1–4 are the model; step 5 is the data migration and is the bulk.

### Acceptance criteria

- `enums.json` carries `document_kind`, `document_status` (+ `adr_status`, `paper_status` subsets), and `doctrine_tier`; all `$ref`-able and fail-closed.
- `.specs/META/` holds a header schema per modeled class; `.specs/` artifact types carry non-null `schema_ref`.
- The CCC fires on a `draft` document cited by an `accepted` artifact, and on an `accepted` ADR lacking `grounding`/`supersedes`.
- Every modeled `.specs/` document validates against its class schema; the free-text `**Status:**` tail is gone.
- #627, #616, #473, #469 close against this ADR.
