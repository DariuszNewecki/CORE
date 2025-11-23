# Phase 1 Delivery — Governed Autonomous Development (A1)

This document describes the **final, corrected, production-accurate** delivery plan for **Phase 1 (A1)** of CORE’s autonomous development model.

Phase 1 is the transition from a static system to a fully governed autonomous development pipeline — the state CORE is in today.

This version replaces all older drafts and removes deprecated concepts (daemon, legacy flows, outdated directory structures).

---

# 1. Phase 1 Goals

Phase 1 establishes CORE’s baseline of **safe, governed autonomy**:

* Crate-based autonomous development
* Context-aware code generation
* Reliable validation (formatting, linting, syntax checks, tests)
* Full constitutional audits
* Mandatory manual integration of crates
* Knowledge Graph extraction and sync
* Traceability through IDs and metadata

Phase 1 delivers the minimum required capabilities for CORE to function as a self-aware, self-healing, governed software system.

---

# 2. What Phase 1 Delivers

## 2.1. Crate Pipeline

A controlled sandbox where all autonomous output is stored.

Includes:

* crate creation service
* crate metadata model
* deterministic folder layout:

  ```
  .core/crates/<crate_id>/
      intent.json
      changes/
      validation_output/
      audit_output/
  ```

No agent may write directly into `src/`.

---

## 2.2. Context Builder

The context builder extracts:

* relevant source files
* dependencies
* symbols
* capabilities
* rules from `.intent/`

Implemented under:

```
src/services/context/builder.py
src/services/context/providers/*
```

This ensures the Will (agents) receives structured, governed context.

---

## 2.3. Autonomous Developer (Will)

Phase 1 delivers a functioning:

* Planner Agent
* Coder Agent
* Cognitive Orchestrator

Located under:

```
src/will/agents/
src/will/orchestration/
```

Agents:

* interpret developer intent,
* generate code/tests,
* produce explanations,
* operate only inside crates.

---

## 2.4. Validation Pipeline (Body)

Ensures all generated code meets baseline standards:

* Black formatting
* Ruff linting
* Syntax validation
* Pytest execution

Located in:

```
src/services/validation/
```

Failures result in immediate crate rejection.

---

## 2.5. Constitutional Auditor (Mind)

The Mind enforces CORE’s rules.

Checks include:

* file headers
* import rules
* domain boundaries
* ID & capability hygiene
* drift detection
* schema validation
* security rules

Located in:

```
src/mind/governance/
```

A failing audit **blocks integration**.

---

## 2.6. Knowledge Graph (Symbols + Capabilities)

Phase 1 includes:

* symbol indexing
* capability extraction
* vector storage (if configured)

Stored in `.intent/knowledge/`.

Maintained through:

```bash
poetry run core-admin manage database sync-knowledge
```

---

## 2.7. Manual Integration Workflow

After a crate is accepted, the developer must:

1. Inspect the generated files
2. Copy them into `src/`
3. Run fixes + knowledge sync
4. Audit again
5. Commit

This enforces **human oversight**.

---

# 3. Requirements Completed in Phase 1

| Requirement                     | Delivered? | Notes                              |
| ------------------------------- | ---------- | ---------------------------------- |
| Safe autonomous code generation | ✔          | Crates only, no direct writes      |
| Validation pipeline             | ✔          | Formatting, linting, syntax, tests |
| Complete audit pipeline         | ✔          | 40+ constitutional checks          |
| Knowledge Graph                 | ✔          | Symbols + capabilities + vectors   |
| Manual integration              | ✔          | Required step in workflow          |
| Governance enforcement          | ✔          | `.intent/` fully controls system   |
| CLI orchestration               | ✔          | `core-admin develop feature`       |

All A1 requirements are now complete.

---

# 4. Core CLI for Phase 1

### Develop a new feature

```bash
poetry run core-admin develop feature "Add X"
```

### Run audit

```bash
poetry run core-admin check audit
```

### Sync knowledge

```bash
poetry run core-admin manage database sync-knowledge
```

### Fix metadata

```bash
poetry run core-admin fix ids --write
poetry run core-admin fix code-style --write
```

---

# 5. Implementation Details

## 5.1. Directory Structure

Phase 1 uses the modern layout:

```
src/
├── api/
├── body/
├── features/
├── mind/
├── services/
├── shared/
└── will/
```

All features integrate cleanly across these domains.

---

## 5.2. Internal Data Contracts

### Crate Metadata

Defines:

* original intent
* related files
* validation results
* audit results
* agent metadata

### Context Bundles

Contain:

* logic fragments
* rules
* symbol traces
* dependency groups

### Capability Mapping

Used for test generation and refactoring suggestions.

---

## 5.3. Tests

Phase 1 requires:

* deterministic tests for validators
* coverage for planners and coders
* resilience tests for audits
* integration test: crate → validation → audit → accept

---

# 6. Acceptance Criteria for Phase 1

Phase 1 is considered complete when:

* All autonomous code passes validation
* All crates produce reproducible outputs
* All agent behavior is traceable
* All audit policies are active and enforced
* `.intent/` is fully authoritative
* Knowledge Graph sync works reliably
* No part of the system performs ungoverned actions

Phase 1 is **already complete** in your current codebase.

---

# 7. Summary

Phase 1 establishes:

* safe autonomy,
* strict governance,
* transparent traceability,
* clean architecture,
* and the full baseline needed for future autonomous evolution.

CORE now has everything needed to begin Phase 2 (Intent-Aware Agents).

Next:
`03-restructure-plan.md`
