---
kind: adr
id: ADR-080
title: ADR-080 — Filesystem-operation-class vocabulary split
status: accepted
---

<!-- path: .specs/decisions/ADR-080-fs-op-class-vocabulary-split.md -->

# ADR-080 — Filesystem-operation-class vocabulary split

**Date:** 2026-05-31
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (vocabulary-split session 2026-05-31)
**Grounding paper:** `papers/CORE-Vocabulary.md` (one term, one definition, one spelling — and its corollary: one *spelling* per *meaning*; conflating two meanings under one spelling violates the same discipline as the reverse)
**Related:** ADR-068 (`.intent/taxonomies/` + `.intent/META/enums.json` pattern), ADR-077 (config-driven protected-namespace access — declares the audit-side taxonomy `filesystem_operations.yaml`), ADR-078 D5 (first-materialization clause for `fs_operation_class`), Issue #489 (the `no_direct_writes` convergence work whose unblock chain runs through ADR-077 §6 step 1, which runs through this ADR)

---

## Context

`.intent/META/enums.json` `fs_operation_class` currently carries this description:

> Operation-class vocabulary used by both `.intent/taxonomies/filesystem_operations.yaml` (call-name → op-class) and `.intent/taxonomies/operational_capabilities.yaml` (per-capability `fs_profile` keys). Same spelling at both surfaces; no pluralization or synonym variants. Authority: ADR-077 + ADR-078. First-materialization: whichever ADR's implementation lands first creates this entry; the second no-ops (per ADR-078 D5 first-materialization clause).

Its values are `[read, create, modify, delete]`.

This description encodes two claims:

1. **Same spelling at both surfaces** — one closed vocabulary, used identically.
2. **First-materialization no-ops the second** — whichever ADR's implementation lands first wins the enum; the other ADR's implementation accepts it.

Both ADRs were accepted before either's taxonomy YAML was authored. ADR-078 won the materialization race and wrote the 4-way decomposition `read/create/modify/delete` — the **write-axis** split, exactly what `operational_capabilities.yaml` `fs_profile` needs to express "this capability may modify but not delete."

ADR-077 §2 lists a different op-class vocabulary for the call-name → op-class taxonomy:

| op-class | meaning | anchor call |
|----------|---------|-------------|
| `read` | reads file content from disk | `Path.read_text` |
| `traverse` | enumerates directory entries | `Path.glob` |
| `parse` | parses structured content from a path-typed argument | `yaml.safe_load(path)` |
| `write` | mutates filesystem state — content, structure, or metadata | `Path.write_text` |
| `neutral` | pure construction with no filesystem effect | `Path("x")`, `os.path.join` |

This is a **read-axis** split (read/traverse/parse distinguish what kind of read), with `write` left as a single class and `neutral` added for non-FS calls. It is what an audit-time call-name taxonomy needs: `Path.glob` is not the same audit subject as `Path.read_text`; `yaml.safe_load(p)` against a protected namespace is its own classification; `Path("x")` is neither, and the audit needs to declare so.

The unification clause and the first-materialization clause were drafted in anticipation that the two surfaces could share one closed vocabulary. They did not survive examination. The two surfaces are decomposing on **different axes for different jobs**:

- `operational_capabilities.fs_profile` — write-axis decomposition for authorization (`create`/`modify`/`delete` matter for chokepoint policy; the read-axis collapses to `read`).
- `filesystem_operations.yaml` — read-axis decomposition for audit completeness (`traverse`/`parse` matter for surfacing distinct call classes; the write-axis collapses to `write` because `forbidden_classes: [write]` is the policy shape).

Either ADR-077 must lose the read-axis distinctions (and ADR-077 §3's `pathlib.Path` completeness check loses analytic resolution), or ADR-078 must extend the enum to a union that conflates two different axes, or the vocabulary splits. ADR-077 §2's table is not negotiable governance: it was a deliberate audit-vocabulary choice. ADR-078 D5's 4-way is not negotiable governance: it was a deliberate authorization-vocabulary choice. The unification was an assumption, not a decision.

This ADR retires the unification clause, declares two enums for two different surfaces, and reinterprets the §6 step 1 sequencing of ADR-077 to consume the new enum rather than the existing one.

## Decisions

### D1 — Two enums, not one

`.intent/META/enums.json` carries two operation-class enums:

- **`fs_operation_class`** (existing, unchanged values) — `[read, create, modify, delete]`. Sole consumer: `operational_capabilities.yaml` `fs_profile` keys. Authority: ADR-078.
- **`fs_audit_op_class`** (new) — `[read, traverse, parse, write, neutral]`. Sole consumer: `filesystem_operations.yaml` per-call-entry `op_class` field. Authority: ADR-077.

Each surface `$ref`s its own enum; fail-closed on empty. Neither enum extends the other; neither enum is a subset of the other; their intersection is `{read}` and that intersection is not a unification — it is a coincidence of spelling on the only op-class that is unambiguously the same operation under both axes.

### D2 — The unification clause is retired

`fs_operation_class`'s description is amended to drop the cross-surface unification claim:

> Operation-class vocabulary for the write-axis decomposition used by `operational_capabilities.yaml` per-capability `fs_profile` keys. Authority: ADR-078. **Not** the audit-time call-name vocabulary — that lives in `fs_audit_op_class` (ADR-080), which uses a separate read-axis decomposition for the `filesystem_operations.yaml` taxonomy declared by ADR-077. The two surfaces' op-class vocabularies are deliberately distinct because they decompose on different axes for different jobs (authorization vs audit completeness). Loader: `src/shared/infrastructure/intent/operational_capabilities.py` reads this enum's values to derive the expected `fs_profile` key set; drift between the YAML's keys and this enum is a load-time failure.

The first-materialization clause in the original description was operative only for the unification scenario it referenced. With unification retired, first-materialization no longer carries cross-ADR meaning. It stays on the historical record (this ADR's Context section) as the original reasoning, not as a live rule.

### D3 — `fs_audit_op_class` enum entry

The new entry in `.intent/META/enums.json`:

```json
"fs_audit_op_class": {
  "description": "Operation-class vocabulary for the audit-time call-name → op-class taxonomy used by .intent/taxonomies/filesystem_operations.yaml. Read-axis decomposition (read/traverse/parse distinguish what kind of read) with write left as a single class and neutral for non-FS calls. Authority: ADR-077 §2, ADR-080. Not the same vocabulary as fs_operation_class — the two surfaces decompose on different axes for different jobs; see ADR-080. Loader: src/shared/infrastructure/intent/filesystem_operations.py reads this enum's values to validate per-call-entry op_class declarations; values outside this enum are a load-time failure.",
  "type": "string",
  "enum": [
    "read",
    "traverse",
    "parse",
    "write",
    "neutral"
  ]
}
```

Ordering matches ADR-077 §2's anchor-call table (read → traverse → parse → write → neutral). Stability of order matters for tooling that diffs the enum across edits; the order is part of the closed-vocabulary contract.

### D4 — ADR-077 §2 stands as written; its enum reference resolves to `fs_audit_op_class`

ADR-077 §2 says:

> op-class enum: declared in `.intent/META/enums.json`, `$ref`-ed, fail-closed on empty.

The enum reference was ambiguous between `fs_operation_class` and an unspecified future enum. This ADR resolves the ambiguity: ADR-077's "op-class enum" is `fs_audit_op_class`. No edit to ADR-077's text is required; this ADR is the reconciliation record.

The corrigendum is recorded here, not in ADR-077, to preserve ADR-077's accepted state as the standing constitutional statement of its audit vocabulary. ADRs are append-only law; reconciliation goes in the later ADR per the precedent ADR-074 D13 set, where ADR-073's `failure_modes` shape was amended ("list" → "mapping") from the later ADR rather than by editing ADR-073 in place.

### D5 — ADR-078 D5's first-materialization clause is scoped down

ADR-078 D5 introduced first-materialization as a coordination mechanism between two ADRs that were both authoring vocabularies. With ADR-080's split, that mechanism no longer governs anything. It remains valid as a general pattern for cases where two ADRs are authoring **the same** vocabulary (e.g. independent enum extensions); it does not extend to **different** vocabularies that share a description claim. ADR-078 D5's text stands; its scope is the cross-ADR coordination on `fs_operation_class` specifically, completed when ADR-078 materialized it.

### D6 — Sequencing of dependent work

ADR-077 §6 step 1 (land `filesystem_operations.yaml`) was implicitly blocked on this vocabulary decision. With this ADR accepted and `fs_audit_op_class` landed, ADR-077 §6 step 1 proceeds: classify `pathlib.Path` via introspection, curate the `os`/`shutil`/`tempfile`/`open` watched set, author the loader, ship the YAML green. Issue #489 (`no_direct_writes` migration) is unblocked transitively once §6 step 1 ships.

## Consequences

- One vocabulary becomes two. The cost is one extra enum entry in `.intent/META/enums.json` and one extra mental load-bearing dimension when reading a future ADR that touches FS classifications: which enum am I in?
- Both ADRs remain Accepted as written. The reconciliation is durable here, not patched into either source ADR.
- ADR-077 §6 step 1 (taxonomy + loader + completeness check) becomes the next discrete unit of work; it is no longer waiting on a vocabulary decision.
- Future ADRs that introduce a third FS-classification surface (none anticipated) inherit the precedent: vocabularies follow surfaces, not the other way around. The `feedback_enum_subset_canonicalize_and_fail_closed` discipline applies to each enum independently; there is no cross-enum subsetting.
- The discipline this ADR exemplifies: when a unification claim doesn't survive the material differences between two surfaces, the unification was the bug, not either surface. This is the inverse of the `vocabulary_canonical_store`-vs-`enums.json` category error captured in the surface ledger (ADR-077 §2): there, two surfaces were forced into one store; here, two vocabularies are being separated into two stores. Same discipline, opposite direction.

## Alternatives considered

- **(b) Extend `fs_operation_class` to the union `[read, traverse, parse, create, modify, delete, neutral]`** and have each YAML classify against its own subset. Rejected: the enum's contract is "what op-classes can a row at this surface declare?" — and that contract is meaningful only if the enum represents the full vocabulary of *that* surface. A union enum makes both surfaces' validation weaker (each surface accepts spellings the other rejects), and the cross-surface description is back to claiming a unification it cannot deliver. Conflates the two axes the split is designed to separate.
- **(c) Amend ADR-077 to the existing 4-way `[read, create, modify, delete]`** vocabulary. Rejected: collapses `Path.glob`, `Path.read_text`, and `yaml.safe_load(path)` into the same op-class, which sacrifices the §3 introspective completeness check's analytic resolution and weakens the §6 step 3 blocking policy's ability to express `forbidden_classes: [write]` (which already maps to the union `create|modify|delete` in the existing enum — workable, but loses the read-axis distinctions ADR-077 §2 introduced deliberately).
- **(d) Keep the unification claim and force the YAML authoring to pick a side at materialization.** Rejected: this is the assumption that didn't survive contact. The two surfaces have already-declared different vocabularies in their accepted ADRs; the unification was a forward-looking assertion, not a settled choice.

## Verification

- `.intent/META/enums.json` carries both `fs_operation_class` (unchanged values, description amended per D2) and `fs_audit_op_class` (new entry per D3).
- `operational_capabilities.yaml` loader (`src/shared/infrastructure/intent/operational_capabilities.py`) continues to derive its `fs_profile` key set from `fs_operation_class.enum`; no loader change required (already shipped against this enum).
- ADR-077 §6 step 1's `filesystem_operations.yaml` schema declares per-entry `op_class` validated against `fs_audit_op_class.enum`; loader at `src/shared/infrastructure/intent/filesystem_operations.py` (to be authored as part of §6 step 1) consumes the new enum.
- ADR-077 §3's introspective completeness check classifies each watched call into one of the five `fs_audit_op_class` values; remediation `manual_review` per ADR-077 §3.
- `core-admin code audit` PASS after each step ships; no rule silently disabled (`Dispatch` baseline preserved per [[feedback_honesty_gated_audit]]).
- Issue #489 unblocked once ADR-077 §6 step 1 + 2 ship green; this ADR is the prerequisite, not a closer.

## References

- ADR-068 — `.intent/taxonomies/` precedent (fail-closed Python loader; `.intent/META/enums.json` $ref pattern).
- ADR-074 — INTERPRET failure modes. D13 is the precedent for later-ADR reconciliation: it corrected ADR-073's `failure_modes` shape from the later ADR, leaving ADR-073's accepted text intact. ADR-080 applies the same discipline to the op-class vocabulary.
- ADR-077 — Config-driven protected-namespace access. §2 declares `filesystem_operations.yaml`'s op-class vocabulary (the audit-axis decomposition this ADR materializes as `fs_audit_op_class`); §3 declares the introspective completeness check that consumes it; §6 step 1 is the dependent work this ADR unblocks.
- ADR-078 — Operational-Capability Taxonomy Schema. D5 introduced the first-materialization clause that this ADR scopes down (D5 here).
- Paper `CORE-Vocabulary.md` — vocabulary discipline (one term, one definition, one spelling); the corollary discipline this ADR applies is *one spelling per meaning* — two distinct decomposition axes must not collapse to one enum just because their intersection on a single op-class spells the same.
- Paper `CORE-Capability-Scoped-Filesystem-Authority.md` §9 (deferral list — §9 bullet 1 is the operational-capability taxonomy YAML schema fulfilled by ADR-078; §9 bullet 4 is the chokepoint identity-propagation implementation fulfilled by ADR-079; the audit-side taxonomy this ADR's vocabulary belongs to sits adjacent to that deferral list, downstream of ADR-077 §6).
- Issue #489 — `no_direct_writes` migration; transitively unblocked by ADR-077 §6 step 1 + 2 shipping, themselves unblocked by this ADR.
