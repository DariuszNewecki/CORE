<!-- path: .specs/decisions/ADR-023-vocabulary-canonical-store.md -->

# ADR-023: Vocabulary canonical store — paper-first, machine projection derived

**Status:** Accepted
**Date:** 2026-05-04
**Depends on:**
- `.specs/papers/CORE-Constitutional-Foundations.md`
- `.specs/papers/CORE-Deliberate-Non-Goals.md`
- `.specs/papers/CORE-Vocabulary.md`

**Related:** ADR-001, ADR-004, ADR-005

---

## Context

CORE has two artifacts that both claim canonical standing for the same conceptual territory — terms used across the system — and they have drifted:

- `.specs/papers/CORE-Vocabulary.md` — markdown index, three layers (Foundational, Implementations, Failure modes), approximately 45 terms. Self-declared authority: Constitution. Opening declaration: *"If a term is used in CORE but not listed here, it is an undeclared assumption. Declare it here or remove it."*

- `.intent/META/vocabulary.json` — JSON, schema-validated against `vocabulary.schema.json`, 16 terms. Metadata declares `authority: meta` and `status: active`. Each entry carries `term`, `definition`, `not`, `authoritative_paper`, optional `aliases` / `see_also`.

The JSON is a strict subset of the markdown but is not declared as a projection. Terms in the markdown not present in the JSON include `ConstitutionalEnvelope`, `Canary`, `FileHandler`, `IntentRepository`, `RemediationMap`, `Mind`, `Body`, `Will`, plus all of Layer A (`NorthStar`, `UNIX`, `Octopus`, `Document`, `Phase`, `Authority`, `Evidence`, etc.). There is no mechanism preventing further drift in either direction.

This is constitutional debt of the highest order: **drift inside the very mechanism CORE operates to prevent drift.** It is the same failure mode GitHub issue #214 exhibits at the instrument level, occurring at the constitutional level. Resolving it is a precondition for any further additions to either artifact, including the addition of audit-instrument schemas (`AuditStats` etc.) that #214 surfaces as needing constitutional declaration.

Adjacent vocabulary-family artifacts exist and are **not in scope** for this ADR:

- `.intent/taxonomies/capability_taxonomy.yaml` — governed correctly by the four-artifact pattern (paper + data + rules + enforcement). This ADR does not modify or absorb it.
- `.intent/META/enums.json` — referenced by `vocabulary.schema.json` for enum-typed value vocabularies. This ADR does not modify it.
- `.intent/enforcement/config/audit_verdict.yaml` — governs verdict-side audit vocabulary per ADR-005. This ADR does not modify it.

What this ADR resolves is specifically the relationship between `CORE-Vocabulary.md` and `vocabulary.json`. Cross-family integration — whether instrument-emitted schemas like `AuditStats` adopt the same pattern, the capability-taxonomy quartet pattern, or a hybrid — is a downstream question this ADR's resolution makes possible but does not itself answer.

The constitutional posture on internal taxonomies is already established: `CORE-Constitutional-Foundations.md` §6 rejects taxonomies as primitives; `CORE-Deliberate-Non-Goals.md` §3.1 carves out the narrow exception that internal taxonomies serving CORE's own operation have constitutional standing when declared in `.intent/`. This ADR operates entirely inside that carve-out.

---

## Architectural framing

This ADR's mechanical decisions establish, by precedent, a pattern that is broader than vocabulary:

- **`.specs/papers/`** carries a canonical section with strict grammar.
- **A regen command** parses that section and emits a structured artifact under `.intent/`.
- **A loader in `src/`** reads the structured artifact with fail-closed semantics.
- **An audit rule** detects drift between the canonical section and the structured artifact.

Read in that frame, this is not a data-sync mechanism. It is a compilation mechanism, with `.specs/papers/` as source, `.intent/` projections as compiled artifacts, the regen command as compiler step, and the audit rule as type checker. Papers stop being documentation that informs implementation; they become **the source from which a portion of `.intent/` is compiled**.

This framing is implicit in this ADR but consequential well beyond it. Future questions about new machine-readable artifacts under `.intent/` — including the resolution of GitHub issue #214's `AuditStats` question — change shape under this framing: the question becomes *"is there a paper that should be its source?"* rather than *"what new artifact should we author?"*

This ADR does not attempt to formalize that framing as constitutional doctrine. Doing so warrants its own paper (working title: `CORE-Specification-as-Source.md`) which is parked as a follow-up. The pattern is established here by precedent; the paper documents and ratifies it. ADR-023 is the first concrete instance, not the umbrella.

---

## Decision

### D1. CORE-Vocabulary.md is the canonical store.

`.specs/papers/CORE-Vocabulary.md` is the single source of truth for CORE's governance-ontology vocabulary. It is paper-authority, human-authored, and the only place definitions, "not" disambiguations, and authoritative-source pointers are added or revised. Its existing self-declaration as canonical is honored, not redefined.

### D2. CORE-Vocabulary.md gains a strict machine-readable section.

A single section of `CORE-Vocabulary.md`, marked by an explicit fence, is the only content the regen command parses. The fence delimits a strict-grammar table; everything outside the fence is human-readable narrative invisible to the regen.

The canonical-section grammar is:

- Header line: `## Canonical Vocabulary (Machine Section)`
- Followed by exactly one markdown table.
- Required columns, in order: `term`, `definition`, `not`, `authoritative_paper`.
- Optional columns: `aliases`, `see_also`. When present, values are pipe-separated lists in single cells.
- Every cell is non-empty for required columns.
- Every `authoritative_paper` cell is a path under `.specs/papers/` resolving to an existing file.
- No nested tables, no inline images, no HTML tags inside cells.

The fence and grammar are not optional formatting suggestions. A paper-side audit rule (D5 below) fails the audit if the canonical section violates this grammar.

The narrative layered structure of `CORE-Vocabulary.md` (Foundational / Implementations / Failure modes) is preserved as human-facing prose **outside** the canonical section. The canonical section is flat — every term, one row, one table — because the regen output is flat and the canonical section is what gets compiled.

Migration: existing terms are moved into the canonical section as part of this ADR's implementation. The narrative layers above remain as commentary but are no longer the source of any term entry.

### D3. vocabulary.json is a machine projection.

`.intent/META/vocabulary.json` is a generated, not authored, artifact. It exists to give the runtime and audit machinery a structured, schema-validated view of the canonical vocabulary. After this ADR lands, hand-editing `vocabulary.json` is a constitutional violation; all term changes flow through `CORE-Vocabulary.md`'s canonical section and are propagated by regeneration.

The projection is generated by `core-admin intent sync vocabulary` (working command name). It reads the canonical section, validates each row against the grammar in D2, and emits the JSON with the schema declared in `vocabulary.schema.json`.

Three identity fields are added to the projection's metadata:

- `source_hash` — SHA-256 over the literal text of the canonical section (fence-to-fence inclusive). The hash is over the canonical section only, not the surrounding narrative, so editorial changes outside the fence do not invalidate the projection.
- `generated_at` — ISO-8601 timestamp of regen.
- `generator_version` — version of the regen command.

The `vocabulary.schema.json` is amended in this ADR's implementation to require these three fields. The metadata `authority: meta` on the projection continues to declare the projection's *shape and validation* authority. The constitutional standing of the **terms** themselves derives from their authoritative source paper, not from the JSON file.

### D4. The loader is fail-closed with a degraded operating mode.

A single sanctioned reader (working path `src/shared/infrastructure/intent/vocabulary_projection.py`) is the only code path that reads `vocabulary.json`. No other module in `src/` may import the file directly; this is enforced as a structural rule.

The loader's behavior:

- **Healthy** — projection present, schema-valid, hash matches recomputed hash over the current canonical section. Loader returns the term set; runtime operates normally.
- **Drift** — projection present and schema-valid, but hash does not match. Loader returns the term set with a `drift_detected: true` flag; runtime operates normally; the audit rule (D5) fails on this condition.
- **Broken** — projection missing, malformed JSON, or fails schema validation. Loader returns an error sentinel and emits a structured event. Runtime enters **governance-DEGRADED mode**: read-only on the governance surface (no writes via FileHandler, no Proposal execution, no Worker remediation). The audit reports DEGRADED, not FAIL, because the projection's brokenness is instrument failure, not code non-compliance — consistent with ADR-005's tri-state verdict policy.

The loader does **not** fall back to hardcoded defaults. A missing or malformed projection is an instrument failure; producing terms from a fallback would mask the failure and propagate the very drift this ADR exists to prevent.

The DEGRADED mode is not a workaround that lets development continue without the projection. It is a controlled stop with explicit semantics. Restoration is by regen.

### D5. Drift detection and grammar validation are constitutional violations.

Three rules are added under `.intent/rules/governance/`. All three carry severity **ERROR**.

1. **`vocabulary.projection_must_match_canonical`** — fails when:
   - A term exists in `vocabulary.json` but not in `CORE-Vocabulary.md`'s canonical section (orphan projection entry).
   - A term exists in the canonical section but not in `vocabulary.json` (missing projection entry).
   - The projection's `source_hash` does not equal the SHA-256 of the current canonical section (stale projection content).

2. **`vocabulary.canonical_format_must_validate`** — fails when the canonical section in `CORE-Vocabulary.md` violates the grammar declared in D2. This rule is the upstream guard that prevents the regen from being asked to parse malformed input.

3. **`vocabulary.authoritative_source_must_be_paper`** — fails when:
   - Any term entry's `authoritative_paper` field does not resolve to an existing file under `.specs/papers/`.
   - Any term entry's `authoritative_paper` value in the projection does not match the canonical section's value for the same term (which would indicate manual JSON tampering surviving regen, e.g. via a partial-write race).

Per ADR-005's verdict policy, ERROR-severity findings flip the audit to FAIL. Drift in the constitutional vocabulary mechanism is the worst class of drift CORE can experience; it does not merit a softer signal. The DEGRADED-on-loader-broken posture in D4 is distinct from these FAIL conditions: D4's DEGRADED applies when the *instrument* is broken; D5's FAIL applies when the *content* has drifted while the instrument works.

### D6. Regeneration is enforced in CI.

The regen command runs in CI as a gate. A pull request whose `vocabulary.json` is stale relative to its `CORE-Vocabulary.md` (detected by recomputing `source_hash` against the canonical section in the PR's tree) fails the CI build with a deterministic message instructing the contributor to run `core-admin intent sync vocabulary` and commit the result.

The CI gate is upstream prevention; the audit rules in D5 are the runtime backstop. Both are required: CI catches drift before it lands; audit catches drift if CI is bypassed or misconfigured. The pre-commit hook is **not** the enforcement mechanism — pre-commit hooks can be skipped (`--no-verify`) and so cannot bear constitutional weight. A pre-commit hook MAY exist as a contributor convenience, but the CI gate is the authority.

### D7. Scope is governance ontology only; boundaries are enforced by location, not metadata.

This ADR governs the vocabulary of CORE's own concepts — Workers, Findings, Rules, Phases, Authorities, Proposals, Crates, Gates, and similar nouns of the governance model. It does **not** govern:

- Capability vocabularies (already governed by the `capability_taxonomy` quartet).
- Enum-type value vocabularies (already in `.intent/META/enums.json`).
- Audit-verdict vocabularies (already governed by ADR-005 + `audit_verdict.yaml`).
- Instrument-emitted schemas (e.g., `AuditStats` — to be addressed in a follow-up ADR that decides whether such schemas extend the canonical-plus-projection pattern established here, the capability-taxonomy quartet pattern, or a hybrid).

The boundary is enforced **structurally**, not by a `family` field on each term. A term lives in `CORE-Vocabulary.md`'s canonical section if and only if its authoritative source paper is in `.specs/papers/` and is not a paper that owns a separate vocabulary family (currently: `CORE-Capability-Taxonomy.md` and `CORE-Cognitive-Role-Capability-Resource-Taxonomy.md`). A reserved-paper list is maintained as part of this ADR's implementation; the rule `vocabulary.authoritative_source_must_be_paper` (D5) extends to fail if any canonical-section entry's `authoritative_paper` matches the reserved list — that term belongs in the other family's store.

This is location-based discipline, not declarative classification. It is consistent with `CORE-Authority-Without-Registries.md`: authority and scope derive from where things live, not from metadata they declare about themselves.

### D8. The current 16-term subset in vocabulary.json is rejected as canonical evidence.

The terms currently in `vocabulary.json` are not the "right" subset of `CORE-Vocabulary.md` under any declared criterion; they are a historical artifact of the projection being authored by hand at one point in time. After this ADR lands, the regen produces a `vocabulary.json` containing **every** term in the canonical section. The 16-term subset disappears. If a smaller machine-readable view is later judged useful for a specific consumer, that is a derived projection over the full projection, not a curated subset of the canonical store.

---

## Alternatives considered

### Alternative A — vocabulary.json is canonical; CORE-Vocabulary.md is a generated view.

Rejected. This contradicts `CORE-Vocabulary.md`'s own constitutional self-declaration and conflicts with the established pattern that papers in `.specs/papers/` are authoritative for concepts. Moving authority into JSON forces vocabulary authoring through a human-hostile format and demotes a paper that already has institutional weight (ADR-001 records that 42 cross-references to `vocabulary.md` had to be repaired during the `.specs/` reorganization — that weight derives from authoritative role, not format). The current dominance of the markdown in scope (45 vs 16 terms) reflects where the authoring has actually been happening; this ADR formalizes the de facto practice.

### Alternative B — Federated by family with declared relationships, no canonical/projection split.

Rejected. This accepts current drift as steady state and adds metadata to describe relationships rather than enforcing convergence. It fails the convergence-principle test: drift is permitted to persist as long as documented. CORE's governance posture is to **prevent** drift, not document it. Federation across families is fine and already in place; within a single family (governance ontology terms), one source must be canonical.

### Alternative C — Unified single canonical store across all vocabulary families.

Rejected as overscoped. Collapsing `capability_taxonomy.yaml`, `enums.json`, `audit_verdict.yaml`, and `CORE-Vocabulary.md` into one store is a substantially larger change with unclear net benefit — these families have different shapes, different authoring conventions, and different existing enforcement. Non-Goals §3.1 already permits per-family governance under `.intent/`. The drift this ADR resolves is intra-family (one family with two artifacts), not inter-family.

### Alternative D — Status quo: leave the drift, document it in a paper.

Rejected. Drift is the failure mode CORE is built to prevent. Documenting it does not resolve it. Drift is not a severity gradient — either the constitution governs the surface or it does not.

### Alternative E — Pre-commit hook as the enforcement mechanism for regen freshness.

Rejected. Pre-commit hooks can be skipped (`--no-verify`) and cannot bear constitutional weight. CI is the upstream authority; pre-commit MAY exist as contributor convenience, but the constitutional enforcement is in CI plus the runtime audit rules.

### Alternative F — Family-field metadata for cross-family classification.

Rejected. Adding a `family: governance | capability | enum | audit` field to each term entry imports the federated-vocabulary model the ADR rejects in Alternative B, in miniature. It also conflicts with `CORE-Authority-Without-Registries.md`'s principle that scope derives from location, not from metadata declarations. The location-based mechanism in D7 (reserved-paper list, structural enforcement) is narrower and constitutionally consistent.

---

## Consequences

### Immediate

1. `CORE-Vocabulary.md` gains the canonical-section fence and is migrated to put every term inside it. Existing narrative layers remain as human-facing commentary outside the fence.
2. `vocabulary.schema.json` is amended to require `source_hash`, `generated_at`, `generator_version` in projection metadata.
3. `vocabulary.json` is regenerated from the canonical section. No hand-edits afterward.
4. Three new rules are added under `.intent/rules/governance/`: `vocabulary.projection_must_match_canonical`, `vocabulary.canonical_format_must_validate`, `vocabulary.authoritative_source_must_be_paper`. All severity ERROR.
5. The loader (`src/shared/infrastructure/intent/vocabulary_projection.py`) becomes the sole sanctioned reader, with healthy/drift/broken behavior as specified in D4. A structural rule prevents direct import of `vocabulary.json` elsewhere.
6. The regen command (`core-admin intent sync vocabulary`) is implemented and registered.
7. CI gains a vocabulary-freshness gate that fails the build when `source_hash` mismatch is detected in PR-tree state.

### Downstream

8. **#214 unblocks.** With the canonical-plus-projection pattern established for one vocabulary family, the question "where does `AuditStats` vocabulary live?" becomes a narrower follow-up ADR that decides whether instrument-emitted schemas adopt this same pattern, the capability-taxonomy quartet pattern, or a hybrid.
9. Vocabulary additions become an exclusively-paper edit followed by regeneration. The CI gate catches missed regeneration; the audit rule is the runtime backstop.
10. The architectural ambiguity around "what is the canonical CORE vocabulary" is removed. Future ADRs that touch vocabulary do not have to relitigate it.
11. The compilation framing established here (paper as source, `.intent/` artifact as compiled output, regen as compiler, audit as type checker) is the precedent for future similar mechanisms. A follow-up paper, `CORE-Specification-as-Source.md`, ratifies this framing as constitutional doctrine. That paper is **parked as a separate follow-up**, not in scope for this ADR.

### Risks

12. The regen command becomes critical infrastructure. **Mitigation**: D4's DEGRADED runtime mode and the CI gate together ensure breakage is detected loudly, not silently. The DEGRADED mode is a controlled stop with explicit semantics, not a workaround.
13. Existing `src/` code may import `vocabulary.json` directly outside the new sanctioned loader. A reconnaissance pass during implementation surfaces any such references and migrates them.
14. The canonical-section grammar must be precisely specified or the regen becomes brittle. **Mitigation**: D2 declares the grammar inline in this ADR; the `vocabulary.canonical_format_must_validate` rule (D5) prevents drift in the grammar itself by failing fast on malformed canonical sections.
15. Hash-based drift detection requires the canonical section's text to be reproducible byte-for-byte across writes. **Mitigation**: the regen command writes the canonical section with deterministic formatting (sorted, no trailing whitespace, fixed table column widths). Manual editors are expected to follow the same format; the `canonical_format_must_validate` rule catches deviations.

---

## References

- `.specs/papers/CORE-Constitutional-Foundations.md` §6 — taxonomies rejected as primitives
- `.specs/papers/CORE-Deliberate-Non-Goals.md` §3.1 — internal-taxonomies carve-out
- `.specs/papers/CORE-Vocabulary.md` — the canonical store
- `.specs/papers/CORE-Authority-Without-Registries.md` — scope-by-location, not by metadata
- `.intent/META/vocabulary.json` — the projection
- `.intent/META/vocabulary.schema.json` — the projection's shape constraint
- ADR-001 — `vocabulary.md` cross-reference weight from the `.specs/` reorganization
- ADR-004 — precedent for taming drifting vocabulary across `src/`
- ADR-005 + `.intent/enforcement/config/audit_verdict.yaml` — precedent for tri-state verdict and instrument-failure handling
- GitHub issue #214 — the diagnosis whose investigation surfaced this ADR's context
- Follow-up: `CORE-Specification-as-Source.md` (parked) — ratifies the compilation framing established by precedent here
