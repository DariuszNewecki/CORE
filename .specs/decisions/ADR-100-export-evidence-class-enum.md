<!-- path: .specs/decisions/ADR-100-export-evidence-class-enum.md -->

# ADR-100 — Export-evidence-class enum: pin the E-46 / E-37 boundary as machine-readable vocabulary

**Date:** 2026-06-09
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-09 — drafted under explicit "write to disk as Accepted" authorization at the close of a higher-up discussion on how to pin the F-46/F-37 evidence-class boundary. The discussion was prompted by an external design comment on issue #525 (marywang-aiops) proposing a four-question verifier contract; question #4 — "Is the export scope explicitly audit evidence only, not governed-change evidence?" — surfaced that the boundary exists only in prose, in two places, and is not enumerated anywhere machine-readable.)
**Grounding decisions:**
- ADR-083 D4 — names the boundary in prose: "F-46 is a simpler artifact aimed at non-regulated buyers: it is *evidence of audit*, not *evidence of governed change*."
- ADR-093 D3 — reclassifies F-46 → E-46 and F-37 → E-37 as members of the Extension class (attaches to the engine via published interface).
- ADR-093 D5 — defers the full Extension Manifest paper to "when the first new E-NN entry needs to land after the URS-line." This ADR does not preempt that paper; it pins one enum that is load-bearing for the verifier contract under design on #525.
- ADR-023 — vocabulary canonical store pattern: paper canonical, machine projection derived. `.intent/META/enums.json` is the documented home for enum-typed value vocabularies and is the projection target here.

**Related:**
- Issue [#525](https://github.com/DariuszNewecki/CORE/issues/525) — E-46 design conversation where the verifier-contract spine was anchored and this ADR's enum is referenced as the machine-readable backing for verifier check #4.
- `.specs/papers/CORE-Features.md` §E-46 / §E-37 — the second prose location of the boundary.
- `.intent/META/enums.json` — the file this ADR authorizes a Path-A write to.

---

## Context

### The prose-only drift surface

The boundary that separates E-46 (Cloud audit export, signed — Solo+ commercial) from E-37 (Regulatory export, GxP / EU AI Act — Enterprise+ commercial) exists today only as prose, in two places:

- ADR-083 D4: "F-46 is a simpler artifact aimed at non-regulated buyers: it is *evidence of audit*, not *evidence of governed change*."
- `CORE-Features.md` §E-46 (lines 775–777): "F-46 is *evidence of audit*; F-37 is *evidence of governed change*."

The distinction is load-bearing — it determines what an export manifest may contain, which verifier contract applies, and which buyer-tier surface the artifact attaches to. But neither the manifest schema nor the verifier exists yet, and a future implementer reading only one of the two prose locations could re-invent the vocabulary in ways that drift from the other. Two prose declarations of the same boundary with no canonical projection is exactly the convention-without-enforcement shape the CORE bootstrap discipline exists to prevent.

### Why now

E-46 was unblocked on 2026-06-07 (the F-43 dependency closed via #417). An external design conversation is live on issue #525: marywang-aiops proposed a four-question verifier contract on 2026-06-09 whose question #4 — "Is the export scope explicitly audit evidence only, not governed-change evidence?" — assumes a machine-readable scope field. The governor's response on the issue thread pinned the four-question spine as E-46's working verifier contract and noted as a follow-up that question #4 needs to be a first-class enum on the manifest, not a `scope.md` narrative.

This ADR is the smallest governance step that lifts the boundary into vocabulary. It does not author the Extension Manifest paper (ADR-093 D5 reserves that scope). It pins one enum that is required by the verifier contract under active design.

### What this ADR is and is not

This ADR pins a vocabulary. It is not a manifest schema, not a verifier specification, and not the Extension Manifest paper. The full manifest paper — storage format, mandatory fields beyond scope, lifecycle, signature envelope — remains paper-scope deferred per ADR-093 D5. Future ADRs and the eventual `ExportManifest.json` data contract will reference this enum by canonical name.

---

## Decisions

### D1 — The enum is named `export_evidence_class`

Two members, both lifted verbatim from the prose phrasing in ADR-083 D4 and `CORE-Features.md`:

- `audit_evidence` — the export contains audit findings and (where Solo+ stateful operation is in use) the surrounding proposal context as supporting evidence for those findings. Produced by E-46. Buyer use case: portable evidence artifact for non-regulated audit consumption.
- `governed_change_evidence` — the export contains the full consequence chain of governed mutations (proposal → action → finding closure) formatted for GxP / EU AI Act regulatory submission. Produced by E-37. Buyer use case: regulatory submission package.

The two classes are **mutually exclusive at manifest scope**: a single export declares exactly one `export_evidence_class`. The enum is closed — no `mixed`, no wildcard, no escape value. An export that does not fit either class is a third evidence class that needs its own ADR amending this one with a new enum member.

### D2 — The canonical location is `.intent/META/enums.json`

The enum lands alongside `dry_run_scope`, `finding_resolution_mechanism`, and the other governance-vocabulary enums already canonicalized there. The block is authorized at the close of this ADR as a Path-A confirmed write. Future data contracts (notably the eventual `ExportManifest.json` under `.intent/enforcement/contracts/`) MUST `$ref` this enum by canonical pointer rather than inline a copy — per the [[feedback_enum_subset_canonicalize_and_fail_closed]] discipline (single source by identity, not by content).

### D3 — The boundary the enum enforces is the F-46 / F-37 separation, not the E-NN / F-NN class line

This enum governs what an export *contains*, not where the producing implementation *lives*. E-46 and E-37 are both Extensions per ADR-093 D3, but `export_evidence_class` is the field that prevents an E-46 export from accidentally embedding consequence-chain consequence-chain semantics (drifting into E-37 territory) and vice versa. The verifier reading a manifest checks `export_evidence_class` to determine which acceptance contract applies; refusing a mismatch is the verifier's job, not this enum's.

### D4 — `audit_evidence` is namespace-bounded and disjoint from the rule-coverage usage in `policy_coverage_service.py`

`src/mind/governance/policy_coverage_service.py:67` defines a private method `_load_audit_evidence()` that returns the set of rule IDs that have executed. That is rule-coverage evidence (which rules ran), not export evidence class (what kind of artifact an export is). The two uses are in disjoint domains and do not need renaming. This ADR records the collision so future readers do not assume a relationship.

### D5 — What this ADR explicitly does NOT decide

To keep the ADR scoped, the following are deferred:

- **The full Extension Manifest paper** (ADR-093 D5) — storage format, full field set, lifecycle, signature envelope, hash algorithms. Remains paper-scope deferred. This ADR fixes one field.
- **The `ExportManifest.json` data contract** — to be authored when E-46 implementation lands. It will `$ref` `export_evidence_class` per D2.
- **The verifier specification** — being designed publicly on issue #525. The verifier's check #4 will read this enum; the verifier's internal structure is implementation-scope.
- **Whether E-37's eventual implementation needs additional fields beyond `export_evidence_class = governed_change_evidence`** — almost certainly yes (consequence-chain envelope, submission metadata), but that is E-37's manifest paper, not this ADR.
- **Vocabulary expansion beyond the two values** — if a third evidence class is needed (e.g., an evidence-of-policy-coverage export shape, a Tier-X composite), it requires a new ADR adding the member with explicit grounding. The enum being closed is the enforcement: silent expansion is foreclosed.

---

## Consequences

### Immediate

- `.intent/META/enums.json` gains one new enum block (`export_evidence_class`) with the two members defined in D1 and a per-value disambiguating description matching the `dry_run_scope` precedent.
- The verifier-contract conversation on issue #525 has a canonical vocabulary to reference. The four-question spine's question #4 becomes "manifest declares `export_evidence_class`; verifier check #4 is a single enum-equality comparison rather than prose interpretation."
- The F-46 / F-37 (now E-46 / E-37) boundary is enforceable at schema-validation time once `ExportManifest.json` `$ref`s the enum, not just by reviewer judgment.

### Deferred-but-named

- `ExportManifest.json` data contract — to be authored under a future ADR when E-46 implementation begins.
- Extension Manifest paper (ADR-093 D5) — remains deferred; this ADR is one input the paper will consume but does not exhaust the paper's scope.

### Foreclosed

- Silent vocabulary expansion. Adding a third `export_evidence_class` value requires an amending ADR; downstream consumers can rely on the closed enum.
- Drift between the two prose declarations of the boundary. The next time ADR-083 D4 or `CORE-Features.md` §E-46/E-37 wording changes, the change MUST also reconcile against the enum description in `.intent/META/enums.json`. Three-way prose drift is replaced by two-way prose + one machine-readable canonical.

---

## Verification

- `.intent/META/enums.json` contains a top-level `export_evidence_class` enum with `enum: ["audit_evidence", "governed_change_evidence"]` and a description that names ADR-083 D4, ADR-093 D3, and Issue #525 as authority.
- The intent loader bootstrap accepts the enum without schema error (existing META schema accommodates new enum blocks of this shape; no schema migration required).
- A search for `export_evidence_class` in `.intent/enforcement/contracts/` returns no hits at the time of this ADR — `ExportManifest.json` does not yet exist, and that is correct (deferred per D5).
- The two prose locations (ADR-083 D4 and `CORE-Features.md` §E-46) remain unchanged; this ADR pins vocabulary, not reasoning.

---

## Notes

This ADR was drafted as the pragmatic-yet-CORE-aligned synthesis of three candidate paths discussed in the originating session: (a) post the draft enum as an issue comment only (governance-weight zero, leaves the drift surface open), (b) author this small focused ADR pinning only the enum (the chosen path), and (c) wait for the full Extension Manifest paper (premature delay — ADR-093 D5's trigger has arrived). Path (b) honors the bootstrap-precedes-code discipline at the smallest possible scope: one decision, one enum, two values, both lifted verbatim from existing prose. Option (a) is preserved as a free follow-up — once this ADR is on disk, the enum block can be posted on issue #525 to keep the public design conversation grounded in canonical vocabulary.
