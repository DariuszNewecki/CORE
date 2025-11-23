# Restructure Plan — Consolidating CORE’s Architecture (2025)

This document defines the **modern, precise, governance‑aligned restructure plan** for CORE.
It replaces all legacy drafts and reflects:

* the current Mind–Body–Will architecture,
* the actual `src/` directory layout,
* the shifted role of `.intent/`,
* the deprecation of older concepts (daemon, legacy agents, obsolete pipelines),
* Phase 1 completion and the transition toward Phase 2.

The restructure plan ensures CORE remains coherent, maintainable, and capable of scaling into A2 and A3 autonomy.

---

# 1. Purpose of the Restructure

CORE has grown rapidly. The restructure ensures:

* clarity of responsibilities,
* strict domain boundaries,
* smoother agent orchestration,
* easier onboarding for new contributors,
* correct alignment with constitutional governance,
* simplified internal APIs,
* no functional duplication.

This plan preserves stability while preparing the system for **intent‑aware autonomy (A2)**.

---

# 2. Target Architecture (Stable Today)

The target structure is the one already in place:

```
src/
├── api/              # HTTP interface
├── body/             # CLI + services + crate lifecycle
├── features/         # introspection, autonomy, maintenance, self-healing
├── mind/             # governance, audits, checks
├── services/         # DB, LLMs, context, validation, storage
├── shared/           # pure utilities, config, common models
└── will/             # agents, planners, orchestration
```

The restructure plan ensures all modules fully comply with this division.

---

# 3. Required Restructuring

Below are the transformations needed to ensure perfect alignment.

## 3.1. Consolidate Self‑Healing Logic

Self‑healing logic exists across:

* `features/self_healing/`
* `body/actions/`
* `services/validation/`

**Action:**

* define a single entrypoint for remediations,
* remove duplicate helper logic,
* merge shared utilities into `shared/utils/`.

## 3.2. Centralize Context Providers

Context providers exist across multiple locations.

**Action:**

* move all context providers to `services/context/providers/`,
* unify provider discovery and ordering,
* ensure consistent rule bundling for Phase 2.

## 3.3. Capability & Symbol Consolidation

Capabilities currently flow through:

* introspection services,
* knowledge builders,
* vectorizers.

**Action:**

* ensure all capability metadata lives under one contract,
* remove older legacy capability logic,
* unify the capability mapping pipeline.

## 3.4. Unify LLM client orchestration

There are multiple layers:

* client orchestrator,
* registry,
* provider base classes,
* secrets binding.

**Action:**

* standardize provider initialization,
* ensure error‑safe fallbacks,
* prepare for capability‑aware prompts.

## 3.5. Remove Deprecated Components

Remove everything referencing:

* daemon workflow,
* early “batch” agents,
* unused development patterns,
* old audit logic superseded by Phase 1.

---

# 4. Governance‑Aligned Directory Enforcement

The restructure ensures directories map cleanly to governance domains.

### 4.1. Body

* CLI logic only
* crate pipeline
* validation execution

### 4.2. Will

* planning
* coding
* reviewing
* reasoning orchestration

### 4.3. Mind

* audits
* policies
* schema enforcement
* constitutional validation

### 4.4. Shared

* pure helpers
* zero dependencies on Body/Mind/Will

### 4.5. Features

* reusable vertical subsystems
* introspection
* autonomy
* maintenance
* self‑healing

A strict import direction must be maintained:

```
shared → services → body → features → will → mind
```

Mind must not depend on Will.

---

# 5. Refactoring Tasks (Actionable Checklist)

## 5.1. Remove Legacy or Unscoped Modules

* delete unused helpers in `body/actions/`
* remove orphaned logic in `features/introspection/*`
* remove legacy import rules

## 5.2. Merge Duplicate Logic

* unify YAML loading
* unify AST extraction
* consolidate vectorization utilities

## 5.3. Improve Internal APIs

* formalize contracts between Body ↔ Will ↔ Mind
* ensure consistent use of dataclasses and pydantic models where appropriate

## 5.4. Strengthen Knowledge Sync

* unify indexing → capability extraction → vectorization
* store outputs in consistent schema

## 5.5. Simplify CLI Wiring

* group related commands
* ensure all commands map to one subsystem
* clean unused CLI endpoints

---

# 6. Impact on Autonomy Roadmap

This restructure is critical for:

### Phase 2 (Intent‑Aware Agents)

* agents consuming `.intent/` rules
* capability‑driven planning
* domain‑aligned reasoning

### Phase 3 (Governed Refactoring)

* drift detection
* safe refactor suggestions
* stable structural metadata

### Phase 4 (Knowledge Expansion)

* improved clustering
* capability graphs
* semantic embeddings

Without restructuring, advanced autonomy becomes unsafe.

---

# 7. Migration Plan

### Step 1 — Inventory

* identify duplicate logic
* list orphaned modules
* catalog all context providers

### Step 2 — Removal of Deprecated Code

* strip out daemon references
* remove legacy validation code

### Step 3 — Consolidation

* merge helpers
* move context providers
* collapse capability extraction logic

### Step 4 — Enforcement

* apply import rules
* update `.intent/` boundaries if needed
* re‑audit project

### Step 5 — Knowledge Rebuild

```bash
poetry run core-admin manage database sync-knowledge
poetry run core-admin check audit
```

---

# 8. Completion Criteria

The restructure is considered complete when:

* no duplicate logic remains,
* context providers unified,
* capability mapping is single‑source,
* only one LLM orchestration path exists,
* directories enforce governance boundaries,
* audits show no architecture drift.

---

# 9. Summary

This restructure plan ensures CORE is:

* clear,
* maintainable,
* governance‑aligned,
* architecture‑consistent,
* prepared for A2 and A3 autonomy.

It closes the gap between early prototypes and the long‑term stable platform CORE is becoming.

Next:
`releases/v0.2.0.md` or return to **Index**.
