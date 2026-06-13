---
kind: adr
id: ADR-073
title: 'ADR-073 — Constitutional Coherence Checker: Scanner Redesign'
status: accepted
---

# ADR-073 — Constitutional Coherence Checker: Scanner Redesign

**Status:** Accepted
**Date:** 2026-05-26
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (CCC redesign session 2026-05-26)
**Governing paper:** `.specs/papers/CORE-Governance-Topology.md`
**Supersedes (partial):** ADR-067 D3 (relation taxonomy and LLM invocation model are replaced by the check-class taxonomy in this ADR)
**Preserves:** ADR-067 D1 (storage schema), D2 (CLI surface), D4 (scheduling posture), D5 (dashboard signal)
**Closes:** (governor to assign issue numbers)

---

## Context

**Grounding chain (completed 2026-05-26 pre-acceptance):** UR-07 (Defensibility is Non-Negotiable) primary, UR-06 (Continuous Constitutional Governance) secondary → `CORE-Governance-Topology` §1.1 and `CORE-ConstitutionalCoherenceChecker` §1.1 → this ADR. Both grounding papers were amended this turn to satisfy topology §3 row 1, which was self-unsatisfied at the time the row was declared.

ADR-067 specified the original CCC implementation with a four-relation taxonomy (R1 ADR↔ADR, R2 rule↔northstar, R3 rule↔ADR, R4 cross-document drift). The 2026-05-26 backlog review session produced enough empirical evidence to expose a definition gap. `CORE-Governance-Topology` (accepted 2026-05-26) closed that gap by declaring:

- The directional grid §3 makes R3 (rule→ADR) editorial and R2 (rule→northstar) forbidden. Both are structurally invalid as scanner check classes.
- The R1 proximity heuristic (adjacent ADR numbers are topically adjacent) is wrong — sequencing is by authoring order.
- §10.3 directs suppression of these classes; §10.2 enumerates new check classes the redesigned scanner should enable.

A separate Stage 0 validation experiment confirmed that the topology §6.1 contradiction invariant is detectable via vector-kNN over embedded normative claims, and surfaced one check class — specification-gap — that requires structural cross-reference rather than vector similarity because the conflict is absence-of-operationalization, not opposing claims. Empirical detail of that validation is recorded in `[[project_ccc_redesign_validation]]` memory; the constitutional record needs the fact of validation, not the calibration data.

This ADR records the decisions required to redesign the scanner against the topology grid and the validated mechanisms. Implementation values (cosine thresholds, embedding throughput, worker cadence) are not decided here; they live in the implementation and are tunable subject to telemetry-driven follow-up.

---

## Decision

### D1 — Suppression of structurally invalid check classes

Three relation classes from ADR-067 D3 are constitutionally invalid per topology §10.3 and MUST be removed from new scanner emission:

- **R3** (rule → ADR coverage): row 7 editorial; rules MAY but need not cite ADRs.
- **R2** (rule → northstar coverage): row 9 forbidden; direct rule→UR citation is governance-skip.
- **R1-proximity** (adjacent-ADR pairing): structural premise wrong.

Historical rows under these codes remain readable per D9; the scanner stops producing new ones.

### D2 — Retention: scoped R1

R1 is retained only for ADR pairs with explicit `Relates:` frontmatter declaration, emitted as `R1_SCOPED`. Scoped R1 is a subset of the §6.1 contradiction mechanism (D5), constrained at the pair-membership step. If no `Relates:` pair exists at scan time, the path emits zero candidates — expected behavior, not failure.

**Citation symmetry:** one-directional citation is sufficient to make the pair scope-valid. If ADR-X cites ADR-Y in its `Relates:` frontmatter, the pair (X, Y) is checked under R1_SCOPED regardless of whether ADR-Y cites ADR-X. This reflects the existing precedent in ADR-037 and ADR-038, where later ADRs declare topical links to earlier ones without expecting backfill of predecessor `Relates:` lines.

### D3 — Check-class taxonomy

The redesigned scanner emits candidates under the following relation codes. Each is mapped to its enforcement mechanism. This taxonomy replaces ADR-067 D3's R1/R2/R3/R4 framework.

| Code | Mechanism | Source |
|---|---|---|
| `R1_SCOPED` | Vector-kNN + LLM judgment, constrained to `Relates:` pairs | Topology §10.3 |
| `SAMECONCERN` | Vector-kNN + LLM judgment, full corpus | §6.1 invariant |
| `ROW2_GROUNDING` | Structural grep | §10.2 row 2 |
| `ROW3_CITATION` | Structural + §2.5 marker detection | §10.2 row 3 (operationalizes ADR-049 D2) |
| `ROW4_NAMING` | Structural grep | §10.2 row 4 |
| `SPECGAP` | Structural cross-reference (upstream required-behavior ↔ downstream operationalizing artifact) | New; derived from Stage 0 validation; not explicit in topology §10.2 |
| `VOCABULARY` | Diff against canonical-projection | §6.2 invariant |

ADR-067 D3's R4 (cross-document drift) is folded into SAMECONCERN (normative content) and VOCABULARY (terminology). No new emission of legacy R1/R2/R3/R4 codes.

### D4 — Governance-embedding sync worker

A new daemon worker `governance_embedder` maintains a Qdrant `governance_claims` collection of embedded normative claims harvested from the governance graph. Decisions:

- **The worker is operational-law layer.** Declared at `.intent/workers/governance_embedder.yaml`. Follows the ADR-018 decomposed crawler/embedder pattern.
- **Incremental contract is constitutional.** The worker re-embeds a claim only when its content hash differs from the stored value. Full-corpus re-embed on every cycle is not permitted.
- **Bootstrap is a governor CLI operation, not implicit daemon behavior.** First-time corpus seeding is performed via a governor-invoked CLI subcommand. The daemon does not auto-bootstrap on start. This is a governance-posture decision per the [[feedback_destructive_autonomous_needs_rails_first]] discipline extended to expensive (non-destructive) autonomous operations.
- **Daemon refuses vector-dependent checks without a seeded collection.** SAMECONCERN and R1_SCOPED emit no candidates when `governance_claims` is absent or empty; the run records the cause. Structural checks (ROW2/3/4, SPECGAP, VOCABULARY) operate independently and are unaffected.
- **Disaster recovery is fixture-based.** A governor-invoked export/import path produces a portable artifact that hydrates the collection without consulting the embedding endpoint. Specific subcommand names and file format are implementation.

### D5 — Tiered cosine policy for §6.1 contradiction

For SAMECONCERN and R1_SCOPED, the scanner runs Qdrant kNN against `governance_claims` and gates LLM judgment by cosine score using a **three-tier policy**:

- **High-confidence tier:** pair forwarded to LLM judge for contradiction verdict.
- **Ambiguous tier:** pair forwarded to LLM judge with a prompt variant that explicitly asks whether the pair is contradictory or merely topically adjacent.
- **Below-threshold tier:** dropped before LLM cost is incurred.

The decision is the **policy shape** — tiered, with an explicit adjacency-vs-contradiction distinction in the middle band. Initial threshold values are empirically calibrated from Stage 0 validation and live in the implementation; they are tunable parameters subject to telemetry-driven revision per a future ADR. Specific values are not constitutional content.

### D6 — Structural checks: ROW2_GROUNDING, ROW3_CITATION, ROW4_NAMING

Three structural checks implemented as deterministic grep/parse operations against the governance graph. No LLM; no embeddings.

- **ROW2_GROUNDING:** every accepted ADR cites at least one `.specs/papers/` artifact OR carries a `Supersedes:` declaration (inheriting its predecessor's grounding). Emit on absence.
- **ROW3_CITATION:** every paper § containing §2.5 normative markers cites a `.intent/rules/...` path OR carries an aspirational/TBD/deferred marker within the section. Emit on absence. Operationalizes the ADR-049 D2 constitutional obligation that has been declared-but-unenforced.
- **ROW4_NAMING:** every artifact under `.intent/` (excluding `META/`) is named in at least one accepted ADR's D-text OR predates topology paper acceptance (grandfathered per §11 backfill-on-touch). Emit on absence. The grandfather signal is the artifact's first-appearance date in git history (`git log --diff-filter=A --format=%aI -- <path> | tail -1`), compared against the topology paper's acceptance date (2026-05-26). Filesystem `mtime` is not used because it does not survive clone, touch, or sync.

### D7 — SPECGAP: specification-gap check

A check class detecting upstream normative claims (Northstar §, paper §) that declare required behavior with no downstream operationalizing artifact in the enforcement surface. The conflict is absence, not opposition; vector kNN cannot detect it because upstream and downstream artifacts share no vocabulary.

- **Mechanism:** structural cross-reference; no LLM, no vectors.
- **v1 scope:** narrow — phases (interpret/parse/load/runtime/audit/execution) and their failure-mode enums against Northstar normative claims.
- **Coverage expansion** is governor-driven via follow-up ADR.

**v1 detection rule (decision content; specific verb sets live in D10 register):**

For each pair `(N, P)` where N is an upstream-normative paragraph and P is a workflow phase, emit a SPECGAP candidate when all of the following hold:

1. **N qualifies as upstream-normative** — N is nested under a UR section in `.specs/northstar/CORE-USER-REQUIREMENTS.md`, OR N contains ≥1 §2.5 marker per D10.
2. **N is operationally linked to P** — either N's text explicitly mentions phase P (literal substring of phase name or cognate), OR D11's `phase_responsibility.yaml` lists at least one UR cited by N's containing section in P's `operationalizes_urs`. This is the bridge that catches architecturally-mapped (text-implicit) cases like issue #459.
3. **N contains a required-behavior action verb** from the D10 register's `action_verbs:` set.
4. **The phase YAML exists with a non-empty `failure_modes:` list.**
5. **No failure_modes entry overlaps the action-verb signal from condition 3** (literal substring or alias match against the marker register).

### D8 — VOCABULARY: vocabulary invariant check

Per topology §6.2 and the ADR-023 canonical projection. Detection by keyword + cognate-set diff against the canonical vocabulary projection. No LLM. False positives ride the standard CCC triage flow.

### D9 — Schema vocabulary migration

The `core.coherence_candidates.relation` CHECK constraint is migrated to:
- ADD the new codes (R1_SCOPED, SAMECONCERN, ROW2_GROUNDING, ROW3_CITATION, ROW4_NAMING, SPECGAP, VOCABULARY).
- RETAIN legacy codes (R1, R2, R3, R4) read-only for historical-row readability.
- RETIRE legacy codes via follow-up ADR after two production cycles confirm no new-emit drift.

The migration script body is implementation. The decision here is the vocabulary shape and the two-cycle clean-up posture per the [[feedback_closed_enum_no_wildcards]] discipline.

`core.coherence_runs.input_manifest` schema grows to record per-run check-class disposition (which classes were attempted, which succeeded, which were skipped, and why). Runs must be self-describing about which check classes participated; the exact field names are implementation.

### D10 — Shared dependency: §2.5 normative-marker register

Several D-sections (D3 SAMECONCERN/R1_SCOPED harvest, D6 ROW3_CITATION detection, D7 SPECGAP detection, D4 governance_embedder harvest) depend on a shared definition of what counts as a §2.5 normative claim. That definition lives at:

**`.intent/enforcement/config/normative_markers.yaml`**

The register declares the regex-friendly marker set from topology §2.5 (MUST, MUST NOT, SHALL, MAY NOT, never, always, forbidden, prohibited, constitutionally, required, and similar categorical-statement tokens). It is the single source of truth for normative-claim detection across the CCC pipeline.

The register is governance-grade content but operational-class authority: changes are reviewed by the governor but do not require paper amendment, because the markers themselves implement topology §2.5's textual definition rather than altering it. Mutation posture follows the standard `.intent/enforcement/config/` pattern (alongside `action_risk.yaml` and similar).

Topology §2.5's "categorical-statement" clause is intentionally not mechanized in v1. The regex-friendly subset is the v1 detection surface; LLM-judged categorical-statement detection is deferred to a future ADR if the regex-only subset proves insufficient.

### D11 — Phase-responsibility mapping for SPECGAP

The v1 SPECGAP heuristic (D7) requires a bridge between upstream normative claims and the downstream phase artifact that operationalizes them. Where Northstar text does not explicitly name a phase (the common case, including issue #459), the bridge is provided by an explicit phase-responsibility mapping.

**Artifact location:** `.intent/enforcement/config/phase_responsibility.yaml`

**Schema (decision content):**

```yaml
phases:
  <phase_name>:
    operationalizes_urs: [UR-NN, ...]   # URs this phase is architecturally responsible for
    responsible_for: ["one-line concern", ...]   # human-readable responsibility statements
    cross_cutting: false   # optional; if true, phase inherits all URs and is excluded from SPECGAP emission
```

**Coverage requirement:** every phase in `{interpret, parse, load, runtime, audit, execution}` declares at least one `operationalizes_urs` entry OR carries `cross_cutting: true`. Coverage is governor-verified at ADR-073 acceptance.

**Mutation posture:** standard `.intent/enforcement/config/` — governor-reviewed config-YAML edits; no paper amendment required.

**Initial mapping content is governor-authored as part of the implementation arc.** A draft proposal accompanies the SPECGAP code-landing PR; governor reviews and amends before the SPECGAP check goes live in production. This ADR declares the schema and the coverage requirement; the specific UR→phase allocations are governance content that the governor authors with my draft as a starting point.

**Authority class:** the mapping is *operational* — it records architectural responsibility allocations that the governor confirms but does not invent. Disagreement between the mapping and the actual phase implementations is itself a SPECGAP-class drift signal that future tooling should surface.

---

## Alternatives Considered

**A1 — Keep R2/R3, document as advisory.** Rejected. The topology paper makes these structurally invalid, not just noisy. Advisory retention preserves the very failure mode the paper closes.

**A2 — Single cosine threshold instead of tiered policy.** Rejected. The empirical distribution from Stage 0 exhibits three modes (contradiction, adjacency, orthogonal); a single threshold either misses real contradictions in the adjacency band or floods the LLM judge with adjacency pairs. The tiered policy with a middle-band prompt variant is the calibrated response.

**A3 — Defer SPECGAP to a separate ADR.** Considered. SPECGAP uses a distinct mechanism (structural) from §6.1 (vectors) and could ship independently. Included here because the empirical evidence comes from the same validation arc and the implementation scope is small. Can be split downstream if independent complexity emerges.

**A4 — Treat all check classes uniformly via LLM judgment.** Rejected. Structural checks (ROW2/3/4, VOCABULARY) are mechanically checkable; LLM judgment on them costs latency and tokens for a structural question. Reserve LLM judgment for genuine semantic ambiguity.

**A5 — Embed the governance corpus in the existing source-projection collection (ADR-018).** Rejected. Schema, keying, and worker mandate differ. Two parallel embedded collections with two parallel workers is the right separation of concerns.

**A6 — Daemon auto-bootstraps the governance_claims collection on first start.** Rejected per D4. Expensive autonomous operations are governor-authorized in CORE, not daemon-implicit. The [[feedback_destructive_autonomous_needs_rails_first]] precedent extends to expensive (non-destructive) operations of this class.

---

## Consequences

**Positive:**
- The scanner stops enforcing doctrine that hasn't been authored. The empirical noise floor from the 2026-05-26 R2/R3 fraction (the ~99% dismissal observed in run `db48491b`) drops to zero on new runs.
- New check classes are mechanically grounded in topology §10.2 (and D7 in Stage 0 evidence), not in convention.
- The governance-embedding sync worker becomes a first-class daemon component, parallel to source-projection per ADR-018.
- Bootstrap-as-governor-CLI matches CORE's existing posture for expensive autonomous operations and preserves the daemon's autonomy boundary.

**Negative:**
- Schema migration retains legacy R1–R4 in the CHECK constraint pending two-cycle clean-up; a known [[feedback_closed_enum_no_wildcards]] tension that follow-up ADR closes.
- SPECGAP's v1 scope is narrow; coverage expansion drives future ADR work.
- The tiered cosine policy's threshold defaults will require telemetry-driven retuning as the corpus grows; this is anticipated, not a defect.

---

## Non-Goals

- This ADR does not author the topology paper. That paper is accepted; this ADR operationalizes it.
- This ADR does not specify LLM prompt templates for SAMECONCERN or R1_SCOPED. ADR-067 D3's prompt contract is preserved as the implementation reference.
- This ADR does not implement automated daemon triggering of `core-admin coherence check`. ADR-067 D4's posture (manual + change-detected) is preserved.
- This ADR does not specify the pattern register for topology §6.3 logic invariant. §6.3 remains aspirational per the topology paper.
- This ADR does not modify ADR-067 D1 (storage tables), D2 (CLI surface), D4 (scheduling), or D5 (dashboard signal). Only D3 is superseded.
- This ADR does not specify embedding throughput targets, worker cadence values, cosine threshold numbers, or migration SQL. Those are implementation.

---

## Verification

ADR is considered Implemented when ALL of the following hold:

1. `src/mind/coherence/checker.py` emits no R1/R2/R3/R4 on new runs; only the D3 taxonomy.
2. `R1_SCOPED` path operates only against ADR pairs carrying `Relates:` frontmatter; parity test against a `Relates:`-declared fixture.
3. `governance_embedder` worker declaration exists at `.intent/workers/governance_embedder.yaml`, registered, heartbeating, producing `governance.embed.complete` blackboard reports.
4. Governor-invoked bootstrap and export/import CLI paths exist; daemon does not auto-bootstrap.
5. Daemon refuses SAMECONCERN/R1_SCOPED with actionable cause when `governance_claims` is absent; structural checks emit normally.
6. The five 2026-05-26 confirms from run `db48491b` are recoverable under SAMECONCERN or R1_SCOPED by the new scanner.
7. The interpret-phase/northstar gap (issue #459) is detected by SPECGAP via the D11 phase-responsibility mapping (UR-03 → interpret-phase bridge declared in the initial mapping). Detection does not require Northstar text to mention `interpret` explicitly.
8. Schema migration applied; relation CHECK constraint matches D9.
9. `.intent/enforcement/config/normative_markers.yaml` (D10) and `.intent/enforcement/config/phase_responsibility.yaml` (D11) exist; D11 has an entry per phase in `{interpret, parse, load, runtime, audit, execution}` with either `operationalizes_urs` populated or `cross_cutting: true`.

---

## Revisit Triggers

- Cosine threshold defaults: after three production runs producing per-tier histograms, follow-up ADR tunes.
- Legacy relation codes (R1–R4): retire from the CHECK constraint after two production cycles with no new-emit drift.
- SPECGAP coverage: expand beyond phase-failure-modes when v1 stabilizes in production.
- Bootstrap throughput becomes infeasible at corpus scale: investigate alternative embedding mechanisms via separate ADR.

---

## References

- Governing paper: `.specs/papers/CORE-Governance-Topology.md` (§3 directional grid, §6 invariants, §10.2 new check classes, §10.3 suppressions)
- Grounding paper: `.specs/papers/CORE-ConstitutionalCoherenceChecker.md` (CCC purpose and authority)
- ADR-067 — original CCC implementation; D3 superseded; D1/D2/D4/D5 preserved
- ADR-018 — decomposed crawler-embedder pattern grounding D4
- ADR-049 D2 — Paper→Rule constitutional direction; D6 ROW3_CITATION operationalizes the existing-but-unenforced obligation
- ADR-023 — vocabulary canonical store grounding D8
- ADR-066 — unmapped-rules invariant; precedent for the "silence is not a valid signal" framing applicable to SPECGAP
- Issue #459 — interpret-phase/northstar specification gap; the empirical case grounding D7
- 2026-05-26 CCC backlog clearance — empirical population grounding D1
- Stage 0 validation outcome (numeric calibration archived in `[[project_ccc_redesign_validation]]` memory)

---

## Note — 2026-05-27 (per ADR-074 D13 corrigendum)

D7 condition 4 reads:

> The phase YAML exists with a non-empty `failure_modes:` list.

Per ADR-074 D2, `failure_modes:` is declared as a mapping (failure-class → response-strategy), not a list. The condition reads:

> The phase YAML exists with a non-empty `failure_modes:` mapping.

D7's logic is unchanged: condition 5's action-verb coverage check iterates the response-strategy surface, which is identically iterable from a map's `.values()` collection as from a list's elements.

Authoritative artifact: ADR-074 §D2, §D13.
