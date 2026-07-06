---
kind: adr
id: ADR-143
title: "ADR-143 — Symbols-Drift: Governed-Anchor SSOT and Source–Graph Staleness Semantics"
status: accepted
---

<!-- path: .specs/decisions/ADR-143-symbols-drift-anchor-ssot.md -->

# ADR-143 — Symbols-Drift: Governed-Anchor SSOT and Source–Graph Staleness Semantics

**Date:** 2026-07-06
**Status:** Accepted
**Authority:** Architectural
**Band:** B — Core Architecture
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-07-06f)
**Grounding:** ADR-057 D5 (`/v1/status/drift` three-scope contract); ADR-078 D6
(`operational_capabilities.yaml` chokepoint grammar); #500 (phantom `project_manifest`
retired); #503 (symbols-drift SSOT undefined)
**Closes:** #503 (D1 — this ADR + stub update); D2 + D3 tracked in #503

---

## Context

### Three scopes, one broken

ADR-057 D5 specified that `/v1/status/drift` answers three orthogonal questions —
**vectors**, **symbols**, **guard** — each representing a different kind of
declared-vs-actual gap.

- `vectors`: implemented and available — Qdrant collection presence check.
- `guard`: undefined — see #502.
- `symbols`: implemented with `{"available": false}` honest stub since #500,
  because the original design was wrong.

### What was wrong

`drift_service.run_drift_analysis_async` was diffing two things that are not the same
kind of surface:

| Side | File | Grammar | Size | Purpose |
|------|------|---------|------|---------|
| "Declared" | `.intent/taxonomies/operational_capabilities.yaml` | `^[a-z][a-z_]*\.[a-z][a-z_]+$` (one-dot, lowercase; ADR-078 D6) | 40 entries | **Authorization chokepoint** — what capabilities the filesystem gate will permit |
| "Implemented" | `core.knowledge_graph` via `KnowledgeService` | Free-form, 2+ dots, CamelCase allowed | 174 entries | **Introspection vocabulary** — CapabilityTagger labels for semantic search / cluster analysis |

These are orthogonal surfaces. `operational_capabilities.yaml` is a permission
registry, not a symbol catalog. CapabilityTagger keys are discovery labels, not
authorization tokens. Overlap is structurally zero — because they describe orthogonal
things. No fix to either surface would make them comparable without collapsing their
distinct purposes.

### What industry precedent says

Google, Netflix, Stripe, and Uber all maintain separate registries for authorization
surfaces and introspection/discovery graphs. They never collapse them. The comparison
that matters at the *symbols* layer is:

> **Are the symbols declared in source (the authoritative governance record) consistent
> with what is registered in the runtime symbol graph?**

That is a staleness check — not a vocabulary overlap check.

### The actual SSOT: the `# ID:` anchor system

CORE already has a governed, universally adopted declaration surface for public symbols:
the `# ID: <uuid>` annotation required on every public `def` and `class` in `src/`
(CLAUDE.md, enforced by the `check_symbol_ids` pre-commit hook). As of 2026-07-06,
there are **3,568** such anchors across `src/`.

`core.symbols` is the runtime registration of those same symbols, populated by
`DbSyncWorker` on a ~5-minute cadence. Its primary key (`id`) is DB-generated
(`gen_random_uuid()`). The link between source and graph is `symbol_path`
(e.g. `src/body/atomic/build_test.py::build_test_action`), not the UUID comment.

The correct symbols-drift question is therefore:

> **Is the set of governance-anchored public symbols in source consistent with the set
> of symbols registered in `core.symbols`?**

---

## Decision

### D1 — Formally retire the `operational_capabilities.yaml`-vs-knowledge-graph comparison

`operational_capabilities.yaml` is the filesystem-authority chokepoint surface.
It MUST NOT be used as the declared-symbol SSOT for drift analysis. The phantom
`project_manifest` policy load in `drift_service.run_drift_analysis_async` is
retired permanently. The function body is replaced with the new implementation
in D3.

`CapabilityTagger` keys remain unchanged — they are internal introspection labels
used by the semantic search and clustering pipeline. They are NOT the symbols-drift
vocabulary.

### D2 — Define symbols-drift as source–graph staleness

Symbols-drift is the symmetric difference between:

**Source set** — every `symbol_path` corresponding to a public `def` or `class` in
`src/**/*.py` that carries a `# ID: <uuid>` anchor on the immediately preceding line.
Extraction is a pure filesystem walk with a regex; no AST required. A symbol is in
the source set if and only if it has a governance anchor.

**Graph set** — every `symbol_path` in `core.symbols` where `file_path` matches
`src/%.py` and `definition_status != 'deprecated'`.

**Drift categories:**

| Category | Definition | Operational meaning |
|----------|-----------|-------------------|
| `unregistered` | In source set, not in graph set | New/modified symbol not yet picked up by DbSyncWorker; expected gap < 5 min after commit |
| `phantom` | In graph set, not in source set | Symbol deleted from source but graph entry persists; DbSyncWorker will clean on next cycle |
| `anchor_missing` | Public `def`/`class` in `src/` exists but has no `# ID:` | Governance deficit; pre-commit hook violation (should not appear in main) |

A healthy system at rest shows `unregistered = 0`, `phantom = 0`, `anchor_missing = 0`.
Transient non-zero `unregistered` or `phantom` counts (< 5 min post-commit) are
expected. Persistent `unregistered` counts indicate DbSyncWorker is stalled.
`anchor_missing` is always a defect.

### D3 — Wire the implementation in three files

**D3a — `IdAnchorScanner`** (new, `src/body/introspection/id_anchor_scanner.py`):
A pure filesystem scanner that walks `src/**/*.py` and extracts all
`(file_path, symbol_path, anchor_uuid)` triples. Uses regex
`^# ID: ([0-9a-f-]{36})$` on the line immediately before `^(async )?def ` or
`^class `. Returns a `frozenset[str]` of `symbol_path` strings for the source set.
No DB access, no LLM, no side effects.

**D3b — `drift_service.run_drift_analysis_async`**: Rewritten to:
1. Invoke `IdAnchorScanner` to get the source set.
2. Query `core.symbols` for the graph set (`file_path LIKE 'src/%.py'`,
   `definition_status != 'deprecated'`).
3. Compute the three drift categories.
4. Return a `DriftReport` with `symbols.unregistered`, `symbols.phantom`,
   `symbols.anchor_missing` counts and (capped) sample lists.

**D3c — `inspect_runner.get_drift_status`**: When `scope in ("symbols", "all")`,
replace the `{"available": false}` stub with a call to the new
`run_drift_analysis_async` result. Stub references to `#503` are retired.

### D4 — Non-decisions (explicit)

- `operational_capabilities.yaml` is unchanged in content, schema, and loader.
- CapabilityTagger and its key vocabulary are unchanged.
- `core.symbols.id` remains DB-generated (`gen_random_uuid()`); no requirement
  to store or match `# ID:` UUIDs in the DB.
- The `# ID:` pre-commit hook is unchanged (it already enforces anchor presence).
- Guard drift (#502) is a separate ADR.

---

## Consequences

**Positive:**
- Symbols-drift now has a well-defined, implementable contract.
- `/v1/status/drift?scope=symbols` becomes genuinely useful: a staleness indicator
  for the DbSyncWorker pipeline.
- `anchor_missing` count gives operators a live view of governance completeness
  (supplementing the pre-commit hook, which only fires at commit time).
- No vocabulary surgery — neither `operational_capabilities.yaml` nor CapabilityTagger
  changes.

**Neutral:**
- `IdAnchorScanner` adds a filesystem walk to the drift endpoint. Walk scope is
  `src/` only (~100 files), expected latency < 200 ms. Acceptable for a
  read-only status endpoint.
- `DriftReport` model gains new fields. Existing callers that only read the
  `capability_drift` field are unaffected; new fields are additive.

**Negative / risk:**
- The symbols-drift definition changes from "capability vocabulary overlap" to
  "source–graph staleness." Callers that depended on the prior semantics (none
  exist; the endpoint returned `available: false`) are unaffected.

---

## Phases

| Phase | Deliverable | Closes |
|-------|-------------|--------|
| **D1** (this ADR) | ADR text + update `get_drift_status` stub comment to reference ADR-143 | #503 D1 |
| **D2** | `IdAnchorScanner` in `src/body/introspection/id_anchor_scanner.py` + unit tests | #503 D2 |
| **D3** | Rewrite `drift_service.run_drift_analysis_async` + enable `inspect_runner.get_drift_status` symbols branch | #503 D3 |

D2 and D3 are implementation work tracked against #503. No further ADR required;
the contract is fully specified above.
