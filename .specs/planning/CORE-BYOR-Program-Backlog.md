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

## 1b. Done 2026-06-20

- **T1 closed** — consumer-mode enforcement verified (see T1 above). Bug B fixed
  (`action_risk.yaml` in starter). T2 unblocked.
- **ADR-119 (Scout) accepted** — BYOR Path 1 renamed Scout; two-phase delivery
  model: `project onboard` (machinery floor) + `project scout` (LLM induction +
  human ratification). Four BYOR path codenames: Scout / Guard / Counsel /
  Generate (sibling). T3 scope corrected to machinery floor only. ADR-108 D1 and
  ADR-111 D1 amended. CORE-BYOR.md §4 table and §8/§9 updated.
- **T5e closed** — ADR-118 fully implemented: `RequirementVerdict` contract (`ae36aa6f`
  D1/D3/D4/D5) + applicability gate detect→suggest→confirm (`1587ebad` D2). Engine
  reshaped to corpus-level verdict unit; silence ≠ verdict; `not_covered` /
  `covered_unauthoritatively` / `not_applicable` / `unavailable` first-class.

## 1c. Done 2026-06-21

- **T5a closed** — ADR-120 accepted + implemented (`a9b19264`): `DocumentRepository`
  adapter interface + `RepositoryAdapterBase` abstract contract (F-41/F-42/F-43
  binding). The seam that decouples domain-specific corpus reading from the engine.
- **T5b closed** — ADR-121 accepted + implemented (`a9b19264`): `document_corpus`
  artifact type, `document_corpus_sensor` worker, `document.run.gap_analysis` action.
  Domain-agnostic rename: `GRCGapAnalysisService` → `DocumentCorpusAnalysisService`
  (alias kept). Pre-existing cross-validation bug in `intent_repository` fixed (identity
  nesting). 7 tests authored, tree clean.
- **T5c closed** — ADR-113 fully implemented: `EvidenceClass` enum (PROVEN/JUDGED/ATTESTED)
  + field on `AuditFinding` (D1); derived from `BaseEngine.evidence_class` class var,
  stamped in `rule_executor` (D2); fail-closed to ATTESTED (D3); `attestation_gate`
  engine surfaces "ATTESTATION REQUIRED" (D4); orthogonal to severity (D5); general
  — code audit + GRC both label findings (D6). All 16 registered engines carry an
  explicit declaration; registry-sweep test enforces this going forward. Surfaces in
  CLI via `check/formatters.py` and `grc/gap_analysis.py`.

## 2. Open threads

### T1 — Verify consumer-mode enforcement  **[DONE — 2026-06-20]**
Confirmed. `code audit --offline` from inside a consumer repo enforces all four
starter rules: 5 blocking + 8 reporting findings, verdict FAIL on planted
violations. Root cause (Bug B): `assisted.apply_diff` / `assisted.validate_diff`
absent from starter's `action_risk.yaml`; fix applied to
`examples/starter-intent/.intent/enforcement/config/action_risk.yaml` and
committed. T2 unblocked.

### T2 — #640 step 2: newcomer docs  **[DONE — 2026-06-20]**
Three surfaces updated in `5f15ded7`: `docs/cold-reviewer.md` dead-end replaced with
`project onboard` + `project scout` instructions; `getting-started.md` BYOR table row +
callout added; `README.md` Quick Start callout updated. `pip install` users caveated
until #674 lands (T3).

### T3 — #674: ADR-108 D3 machinery-in-wheel  **[SCOPE CORRECTED — ADR-119 D9]**
Bundle the **machinery floor only** in the `core-runtime` wheel + loader fallback
so `pip install` adopters can run `project onboard` (Phase A), not only source-tree
runs. The rules layer is never bundled — it is per-repo-inducted by `project scout`
or per-repo-authored; there is no canonical rule set to ship. Unblocks wheel-user
BYOR Phase A. Tracked: issue #674.

### T4 — `work/`-staging airlock for onboard  **[design, deferred by governor]**
Decision deferred: keep "write into the named repo" (dry-run + refuse-if-exists as
the rails) vs. add a `work/<name>/` staging airlock the operator promotes. If
adopted → amend ADR-111 D3 + the implementation. Most relevant to the GRC/regulated path.

### T5 — BYOR-grounded ADRs (`CORE-BYOR.md` §9)

- **T5a** ✅ **DONE 2026-06-21** — Repository adapter interface (ADR-120, `a9b19264`).
- **T5b** ✅ **DONE 2026-06-21** — GRC `document_corpus` type (ADR-121, `a9b19264`).
  Includes `document_corpus_sensor` + `document.run.gap_analysis` action.
  Regulation→Intent residency boundary decided in ADR-116 (catalog as data; `public/`,
  `licensed/`, `internal/` tiers). Domain-agnostic: any document corpus, not GRC-only.
- **T5c** ✅ **DONE 2026-06-21** — Per-finding attestation (ADR-113). All 6 decisions
  shipped; 16 engines declared; registry-sweep test enforces completeness going forward.
- **T5d** — **OPEN, gated on licence procurement** — GRC internal audit corpus pipeline
  (ADR-116 D9). Layout reserved (`grc-catalogs/internal/`, gitignored). Ingestion,
  licence-gate enforcement, corpus-as-input invariant, resolver tolerance. Depends on
  T5b ✅ (provides requirement set). Copyrighted frameworks need held licence; public-domain
  ingest is ungated. No engineering blockers except procuring licences.
- **T5e** ✅ **DONE 2026-06-20** — Verdict unit: requirement-over-corpus (ADR-118,
  `ae36aa6f` D1/D3/D4/D5 + `1587ebad` D2). `RequirementVerdict` + applicability gate.
  (See §1b above.)

---

## 3. Sequencing

**As of 2026-06-21:** T1/T2/T3/T5a/T5b/T5c/T5e are all shipped. The full honesty
stack — Scout induction, document_corpus type, repository adapter, corpus-level
verdict, per-finding provenance label — is live.

Remaining open in priority order:
1. **T5d** (internal corpus) — procurement-gated; no engineering block once a
   licence is held. Can spec the pipeline now.
2. **T4** (airlock) — governor-deferred design decision.

The commercial center of gravity is GRC (governor decision 2026-06-17). Code
self-development runs on a maintenance track.

---

## 4. References

- `CORE-BYOR.md` — the program's shape (grounds the ADRs below)
- ADR-111 — `project onboard` delivers the authored starter (#640 step 1)
- ADR-116 (D7 inventory registry, D8 tier=repo boundary, D9 internal audit corpus → T5d)
- ADR-118 (GRC verdict unit: requirement-over-corpus + applicability gate → T5e ✅)
- ADR-119 (Scout — BYOR Path 1 induction ✅)
- ADR-120 (repository adapter interface — T5a ✅)
- ADR-121 (document_corpus type — T5b ✅)
- ADR-108 (D3 → #674 → T3)
- ADR-075 (namespace), ADR-090 (multi-domain)
- #640 (BYOR newcomer docs — T2), #674 (wheel packaging — T3)
