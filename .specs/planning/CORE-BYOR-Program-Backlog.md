# CORE — BYOR / GRC Program — Open Threads

**Status:** Working backlog (derived, non-authoritative)
**Location:** `.specs/planning/CORE-BYOR-Program-Backlog.md`
**Audience:** Internal — engineering sequencing for the BYOR adoption surface + the GRC commercial wedge
**Created:** 2026-06-17

---

## 0. How to read this

Derived backlog for the BYOR/GRC program. The *shape* is set by `CORE-BYOR.md`
(paper); decisions land as ADRs grounded in it; ship-state is the issues/ADRs
themselves. This doc only sequences what is open after the 2026-06-17 session
that parametrized the obligation layer and ratified + implemented ADR-111.

---

## 1. Done 2026-06-17 (context)

- **Obligation layer parametrized** (`57379c9d`) — code is artifact type #1, not
  CORE's scope; Final Invariant generalized ("never produce *work* it cannot defend").
- **`CORE-BYOR.md`** (paper, draft) — domain-general adoption surface; "Repository"
  is the single parametrization seam; two maturity axes (Autonomy × Reach); GRC
  gap-analysis as the first paid wedge under an honesty guardrail.
- **ADR-111** (accepted) + implemented (`d0418920`) — `project onboard` *delivers*
  the authored starter (machinery floor + 4-rule constitution) into `<target>/.intent/`;
  generator path removed. **#640 step 1 closed**, verified end-to-end.

---

## 2. Open threads

### T1 — Verify consumer-mode enforcement  **[GATE]**
Does the delivered starter actually *enforce* in a consumer repo? `code audit
--offline` from inside an onboarded repo *loaded* the four starter rules but logged
them as "no enforcement mappings." Confirm enforcement (or fix the starter /
F-10 consumer-audit path) **before** any doc promises self-serve. Domain: F-10 /
ADR-108. **Gates T2.**

### T2 — #640 step 2: newcomer docs  **[blocked on T1]**
Point `docs/cold-reviewer.md`'s "no `.intent/`" dead-end at `project onboard`; add a
"govern your own repo" step to README / getting-started. Per ADR-111 D6, MUST NOT
promise the self-serve path until T1 is confirmed (and #674 for `pip install` users).

### T3 — #674: ADR-108 D3 machinery-in-wheel
Bundle the machinery floor in the `core-runtime` wheel + loader fallback so
`pip install` adopters can onboard, not only source-tree runs. Unblocks wheel-user
BYOR. Tracked: issue #674.

### T4 — `work/`-staging airlock for onboard  **[design, deferred by governor]**
Decision deferred: keep "write into the named repo" (dry-run + refuse-if-exists as
the rails) vs. add a `work/<name>/` staging airlock the operator promotes. If
adopted → amend ADR-111 D3 + the implementation. Most relevant to the GRC/regulated path.

### T5 — Remaining BYOR-grounded ADRs (`CORE-BYOR.md` §9)
- **T5a** — Repository adapter interface (the concrete F-41/F-42/F-43 binding).
- **T5b** — GRC document/records Repository type + regulation→checkable-Intent
  representation. The commercial centerpiece; also the hardest part (RegTech).
  - *Regulation→Intent residency split decided in **ADR-116** (proposed 2026-06-19):*
    the catalog is licensed law-as-data, consumed not bundled — `grc-catalogs/{public,
    licensed}`, `licensed/` never in this public repo. Advances T5b's catalog side.
    *Still open:* the document/records **sensor type** (F-42 binding that reads a
    customer's records library) — a sibling slice, not covered by ADR-116.
- **T5c** — Per-finding attestation (proven / judged / attested) — the honesty
  guardrail made mechanical.
- **T5d** — GRC internal audit corpus pipeline (**ADR-116 D9**, ratified 2026-06-20).
  The reasoning substrate the audit engine runs against — distinct from T5b's
  *shipped* catalog. Scope:
  - **Ingestion:** source (e.g. PDF) → extracted text → vector inputs, into a
    per-framework Qdrant collection. Layout fixed by D9
    (`grc-catalogs/internal/<framework>/{source,text,licence.yaml}`); path is
    gitignored + reserved (`131f888b`).
  - **Licence-gate enforcement:** block ingest of a `copyrighted` source's full
    text unless its `internal_use_licence` is satisfied (recorded in
    `inventory.yaml` + `internal/<framework>/licence.yaml`). `public-domain` /
    `official-*-reusable` ingest freely. Ungated copyrighted ingest is a violation,
    not a warning.
  - **Corpus-as-input invariant:** the engine consumes the corpus to produce
    findings + clause citations; it MUST NOT serve stored source text back out
    (preserves D5). Needs an enforceable check, not just intent.
  - **Resolver tolerance:** like `licensed/`, `internal/` may be absent/partial;
    without it CORE runs cite-only and gap-analysis still functions — degraded,
    honest, never silently ungated.
  - *Depends on T5b* (the catalog gives the requirement set the corpus answers
    against) and the Qdrant collection-per-tenant isolation model (per-customer
    licensed corpora never co-mingle). Procurement precondition for copyrighted
    frameworks: CORE holds the commercial/internal-use licence (currently none held).
- **T5e** — GRC verdict unit: requirement-over-corpus (**ADR-118**, accepted 2026-06-20).
  Spans T5b+T5d: the reported unit is one `RequirementVerdict` per requirement over the
  whole corpus, fronted by an applicability gate (detect→suggest→confirm domain;
  out-of-scope surfaced, not dropped). Replaces the per-document judged roll-up shipped in
  Scenario-4 — "silent" stops being a verdict (it's absence-of-evidence), and corpus-level
  `not_covered` / `covered_unauthoritatively` become first-class. Generalizes the ITAM
  heatmap's coverage + authority model. Implementation: the `RequirementVerdict` contract,
  the applicability gate, evidence retrieval/localization, and the engine reshape.

---

## 3. Sequencing

T1 first — cheap, and it gates the on-ramp's honesty. Then T2 (docs) and T3 (#674)
complete code-BYOR end-to-end for all users. T5b is the commercial payoff (GRC) and
the largest effort — where the real RegTech value and the hard intent-representation
problem live; T5a is its prerequisite. T5d (internal corpus) follows T5b and turns
the catalog from a checklist into an evaluable substrate; its copyrighted path is
also gated on a procurement step (licence acquisition), not just engineering. T5e
(verdict unit, ADR-118 accepted) is the contract both T5b and T5d produce verdicts
under — the engine reshape that makes corpus-level coverage honest; it can begin
ahead of the internal-corpus procurement since it is pure engine/design. T4 is
a parallel design call. The commercial
center of gravity is GRC (governor decision 2026-06-17); code self-development runs
on a maintenance track meanwhile.

---

## 4. References

- `CORE-BYOR.md` — the program's shape (grounds the ADRs below)
- ADR-111 — `project onboard` delivers the authored starter (#640 step 1)
- ADR-116 (D7 inventory registry, D8 tier=repo boundary, D9 internal audit corpus → T5d)
- ADR-118 (GRC verdict unit: requirement-over-corpus + applicability gate → T5e)
- ADR-108 (D3 → #674), ADR-075 (namespace), ADR-090 (multi-domain)
- #640 (BYOR), #674 (wheel packaging)
