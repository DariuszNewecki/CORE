---
kind: adr
id: ADR-143
title: "ADR-143 — Symbols-Drift: Governed-Anchor SSOT and Existing-Pipeline Consumption"
status: accepted
---

<!-- path: .specs/decisions/ADR-143-symbols-drift-anchor-ssot.md -->

# ADR-143 — Symbols-Drift: Governed-Anchor SSOT and Existing-Pipeline Consumption

**Date:** 2026-07-06
**Status:** Accepted
**Authority:** Architectural
**Band:** B — Core Architecture
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-07-06f)
**Grounding:** ADR-057 D5 (`/v1/status/drift` three-scope contract); ADR-078 D6
(`operational_capabilities.yaml` chokepoint grammar); #500 (phantom `project_manifest`
retired); #503 (symbols-drift SSOT undefined)
**Closes:** #503 D1

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
things.

### What already exists (reconnaissance finding)

Before implementing anything new, the existing pipeline was audited:

1. **`purity.stable_id_anchor`** (`.intent/rules/code/purity.json`) — audit rule that
   fires on every public `def`/`class` in `src/` lacking a `# ID: <uuid>` anchor.
   Uses `ast.walk()` + `find_symbol_id_and_def_line` (`shared.ast_utility`).

2. **`auto_remediation.yaml`** maps `purity.stable_id_anchor` → `action: fix.ids`,
   confidence 0.91, status ACTIVE.

3. **`fix.ids`** atomic action (`body.atomic.fix_actions`) wraps
   `id_tagging_service.assign_missing_ids` — deterministic AST walk that inserts
   `# ID: <uuid>` above every public symbol missing one.

4. **`ViolationRemediatorWorker`** reads the remediation map, claims
   `purity.stable_id_anchor` findings, and creates proposals for `fix.ids` that
   `ProposalConsumerWorker` executes without LLM involvement.

5. **`DbSyncWorker`** syncs `src/**/*.py` → `core.symbols` on a ~5-minute cadence.
   After a sync cycle, the source-vs-graph gap is closed by construction.

6. **`check_symbol_ids`** pre-commit hook enforces anchor presence at commit time.

The full autonomous loop is: audit detects → remediation map routes → proposal
created → `fix.ids` assigns UUID → committed. No new scanner needed.

### What `operational_capabilities.yaml` is not

It is the filesystem-authority chokepoint surface — a permission registry, not a
symbol catalog. It must not be diffed against the symbol graph. That comparison was
the original bug in the drift service.

---

## Decision

### D1 — Formally retire the `operational_capabilities.yaml`-vs-knowledge-graph comparison

`operational_capabilities.yaml` MUST NOT be used as the declared-symbol SSOT for
drift analysis. The phantom `project_manifest` policy load is retired.

`CapabilityTagger` keys are internal discovery labels, unchanged.

`core.symbols.id` is DB-generated (`gen_random_uuid()`), not the `# ID:` UUID.

### D2 — No parallel scanner

A new `IdAnchorScanner` MUST NOT be built. Detection of missing anchors is owned
exclusively by the `purity.stable_id_anchor` audit rule and its remediation loop.
Building a parallel scanner would duplicate detection, split the signal, and create
two systems that could disagree.

The `# ID:` anchor governance is a closed loop:
`pre-commit hook` → `audit` → `remediation map` → `fix.ids` → committed.
The drift endpoint consumes this loop's output; it does not re-implement it.

### D3 — Wire symbols-drift to existing pipeline output

`inspect_runner.get_drift_status` symbols branch and `drift_service` MUST query
existing blackboard data rather than performing a fresh source scan:

- **anchor coverage**: count of open `purity.stable_id_anchor` violation findings
  in the blackboard (status = `open` or `awaiting_reaudit`)
- **graph staleness**: count of `core.symbols` rows with
  `definition_status = 'pending'` (synced but not yet classified) and the
  timestamp of the last `DbSyncWorker` heartbeat

This consumes the governed pipeline's output with no duplication.

D3 implementation is tracked in #503 and requires no further ADR.

### D4 — Non-decisions (explicit)

- `operational_capabilities.yaml` — unchanged.
- CapabilityTagger and its key vocabulary — unchanged.
- `fix.ids`, `id_tagging_service`, `purity.stable_id_anchor` — unchanged.
- Guard drift (#502) is a separate ADR.

---

## Consequences

**Positive:**
- No parallel systems. The drift endpoint reports what the governed pipeline already
  knows, not a separate computation.
- `operational_capabilities.yaml` is unambiguously an authorization surface, not a
  symbol catalog. Future contributors cannot confuse the two surfaces.
- The existing audit + remediation loop for `# ID:` anchors is the single source of
  truth. Its signal reaches the operator via both the audit dashboard and the drift
  endpoint.

**Neutral:**
- The symbols branch of `/v1/status/drift` remains `{"available": false}` until D3
  is implemented. This is honest — the endpoint does not fabricate data.

**Negative / risk:**
- None. The parallel scanner built and then reverted in this session is not shipped.

---

## Phases

| Phase | Deliverable | Status |
|-------|-------------|--------|
| **D1** | ADR text + retire phantom `project_manifest` reference | Done |
| **D2** | No parallel scanner — decision recorded | Done |
| **D3** | Wire symbols branch to blackboard findings + DbSyncWorker heartbeat | Pending #503 |
