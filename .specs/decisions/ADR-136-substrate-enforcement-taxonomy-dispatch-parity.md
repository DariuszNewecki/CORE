---
kind: adr
id: ADR-136
title: "ADR-136 — Substrate-Enforcement Taxonomy and Dispatch-Parity CCC Check"
status: accepted
---

<!-- path: .specs/decisions/ADR-136-substrate-enforcement-taxonomy-dispatch-parity.md -->

# ADR-136 — Substrate-Enforcement Taxonomy and Dispatch-Parity CCC Check

**Date:** 2026-07-02
**Governing paper:** `.specs/papers/CORE-Enforcement-Completeness.md`
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-07-02)
**Band:** B — Governance Infrastructure
**Grounding papers:** ADR-073 (CCC redesign); ADR-066 (unmapped-rules invariant);
CORE-Instrument-Attestation.md (instrument honesty)
**Related:** External architecture review 2026-07-02 §7c, §8b, §8c

---

## Context

### The PASSIVE_ALIASES problem

`src/mind/logic/engines/registry.py` contains a module-level Python constant:

```python
PASSIVE_ALIASES = {
    "python_runtime", "type_system", "runtime_metric",
    "advisory", "runtime_check", "dataclass_validation",
}
```

When `EngineRegistry.get(engine_id)` is called with one of these names, it silently
redirects to `passive_gate` — an engine whose `verify()` returns `ok=True` always. This
means ~39 enforcement mappings (~18% of the surface) have their rules evaluated by an
engine that can structurally never fail. The mappings are legitimate: these rules are
enforced by substrate (MyPy, Pydantic, Python runtime), not by CORE's audit-time engines.
But the governance decision — *which engine names are substrate-trusted* — lives in a Python
constant with no governance home, no schema, and no attestation that the substrate actually
enforces the claim.

### The rules→dispatch blind spot

The Constitutional Coherence Checker (ADR-073) covers paper→rule gaps (ROW3_CITATION,
SPECGAP) but has no check for the rules→dispatch edge:

- No standing sensor for "which rules have no enforcement mapping"
- No standing sensor for "which mappings route to an unknown engine"
- No proactive visibility into the passive population

The only discovery mechanism is an ad-hoc Python scan (confirmed working in the external
review, ~20 lines). It is not run continuously, its results are not persisted, and it
produces no CCC candidates.

The external review found 97 rules with no mapping entry (#739) — a gap the ADR-066
invariant was designed to prevent. That gap was discovered by the one-off scan, not by the
governance surface.

---

## Decision

### D1 — Substrate-enforcement taxonomy

Create `.intent/taxonomies/substrate_enforcement.yaml`. This file is the canonical
declaration of which engine names delegate to substrate rather than to an audit-time CORE
engine. It replaces the Python constant as the governance source of truth.

Each entry names the substrate surface responsible for enforcement, so future readers can
verify the claim ("MyPy actually catches this") rather than trusting a bare entry.

### D2 — DispatchParityCheck CCC check class

Add `src/mind/coherence/checks/dispatch_parity.py` implementing the `CheckClass` protocol.
`relation = "DISPATCH_PARITY"`. No LLM. No vectors. Pure data reading.

Two sub-checks emitted as candidates:
- **UNMAPPED**: a rule ID present in `.intent/rules/` with no entry in
  `.intent/enforcement/mappings/`. Closing this closes the ADR-066 invariant gap.
- **UNKNOWN_ENGINE**: a mapping entry whose `engine` value is neither a file-backed engine
  discovered by `EngineRegistry` nor an entry in the substrate taxonomy (D1). This catches
  typos and taxonomy drift before they silently no-op.

### D3 — Register DispatchParityCheck in CoherenceChecker

Add to the `checks` list in `checker.py`. It needs only `repo_root`.

### D4 — EngineRegistry loads passive aliases from taxonomy

In `EngineRegistry.initialize()`, after `_path_resolver` is set, load the D1 taxonomy YAML
and replace the runtime `PASSIVE_ALIASES` set with the taxonomy's entry keys. The module-
level constant becomes the cold-start fallback (used before `initialize()` is called).
This ensures the running registry and the governance file cannot silently diverge.

---

## Consequences

**Positive:**
- The substrate-trust decision is now law (`.intent/`) rather than code
- CCC produces standing `DISPATCH_PARITY` candidates for every unmapped rule and every
  unknown engine — the scan that found the 97-rule gap now runs every CCC cycle
- `EngineRegistry.get()` fails loudly (unknown engine, not passive alias) if a mapping
  references an engine name that is neither file-backed nor declared in the taxonomy

**Negative / watch items:**
- Adding a new substrate-delegated engine now requires a taxonomy entry; previously
  adding it to the Python constant was sufficient. This is the intended friction.
- DispatchParityCheck reports only; it cannot block. The CCC "no enforcement power"
  constraint (ADR-073 D1) applies.

---

## Delivery phases

| Phase | Deliverable | Status |
|---|---|---|
| D1 | `.intent/taxonomies/substrate_enforcement.yaml` | Done |
| D2 | `src/mind/coherence/checks/dispatch_parity.py` | Done |
| D3 | `checker.py` — add DispatchParityCheck | Done |
| D4 | `registry.py` — load aliases from taxonomy | Done |
