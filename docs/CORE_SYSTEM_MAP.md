# CORE SYSTEM MAP (CSM)
> Single-page overview of how CORE *behaves* as a system.

## 1. Purpose

This document gives a **human-readable, system-level view** of CORE:

- What workflows exist and what they do
- Which subsystems they touch
- Which patterns and guardrails they follow
- How developers are supposed to “sync” and keep CORE coherent

It is **not** a reference manual or API doc.
It is the **map of the machine**.

---

## 2. High-Level System View

CORE is structured as:

- **Mind** – Governance & rules
  - `.intent/charter/`, `.intent/policies/`, vectorized policies in Qdrant
- **Body** – Execution engine & services
  - CLI commands, context/index builders, coverage tools, symbol graph, etc.
- **Will** – Agents & orchestration
  - Self-healing engines, test generators, (future) A2 orchestrators

At runtime, CORE is mostly **driven by workflows**:

- CLI workflows (e.g. `core-admin context rebuild`)
- Agent workflows (self-healing, coverage remediation)
- Sync rituals (e.g. `make dev-sync`)

This map describes those workflows and the **patterns** that keep them safe.

---

## 3. Workflows

### 3.1 Workflow Legend

Each workflow is described by:

- **ID** – Stable identifier
- **Command / Trigger** – CLI or agent entry point
- **Mode** – `READ_ONLY` or `READ_WRITE`
- **Safety** – `always_safe` / `dry_run_default`
- **Touches** – Main subsystems / data it operates on
- **Notes** – Important behavior / expectations

---

### 3.2 Workflow Catalogue (initial draft)

#### W1 – Inspect Workflows

- **ID**: `workflows_inspect`
- **Command**: `core-admin inspect workflows`
- **Mode**: `READ_ONLY`
- **Safety**: `always_safe`
- **Touches**:
  - Workflow definitions (this document / `.intent/workflows/*` if present)
- **Notes**:
  - Discovery-only: used to *see* what workflows exist and how they’re classified.
  - Must never mutate state.

---

#### W2 – Context Rebuild

- **ID**: `context_rebuild`
- **Command**: `core-admin context rebuild [-dry-run|--write]`
- **Mode**: `READ_WRITE`
- **Safety**: `dry_run_default`
- **Touches**:
  - `ContextService` / `ContextPackage`
  - Symbol graph / index
  - Vector store entries related to code context (if integrated)
- **Notes**:
  - **Pattern**: `inspect → plan (dry-run) → apply (--write)`
  - Default behavior is to **simulate** changes and show what would be rebuilt.
  - `--write` is required to actually persist new context/index state.

---

#### W3 – Coverage Remediation

- **ID**: `coverage_remediate`
- **Command**: `core-admin coverage remediate` (exact name may differ)
- **Mode**: `READ_WRITE`
- **Safety**: `dry_run_default` (recommended)
- **Touches**:
  - Test files under `tests/…`
  - Coverage reports
  - Self-healing / test generation engines
- **Notes**:
  - Uses **ContextPackage** to generate context-aware tests.
  - Runs tests, attempts fixes, and may write new test code.
  - Should follow the same `dry-run by default, explicit write` pattern for future hardening.

---

#### W4 – Policy & Symbols Sync

- **ID**: `policy_and_symbol_sync`
- **Command**: (composed inside `make dev-sync` + dedicated admin commands)
- **Mode**: `READ_WRITE`
- **Safety**: `dry_run_default` (target)
- **Touches**:
  - Symbols index (AST / structural hash)
  - Vectorized policies in Qdrant
  - Any additional embeddings (constitution, patterns, docs)
- **Notes**:
  - Ensures **Mind** (policies) and **Body** (code symbols) are consistent.
  - Intended to be part of the **developer sync ritual** (see Section 6).

---

#### W5 – Self-Healing (Code Correction)

- **ID**: `self_healing_code_correction`
- **Trigger**: Failure in validations/tests, invoked by agent / CLI
- **Mode**: `READ_WRITE`
- **Safety**: `governed_by_policies + tests`
- **Touches**:
  - Source files being corrected
  - Tests related to those files
  - Validation/audit logs
- **Notes**:
  - Uses enriched failure context + policies + ContextPackage when available.
  - Writes changes only when they pass **constitutional audit + tests**.
  - This is CORE’s **A1** self-healing loop.

---

#### W6 – Context-Aware Test Generation

- **ID**: `context_aware_test_generation`
- **Trigger**: Coverage remediation, manual CLI, or agent request
- **Mode**: `READ_WRITE`
- **Safety**: `governed_by_policies + tests`
- **Touches**:
  - Test files under `tests/…`
  - Context services
- **Notes**:
  - Uses `ContextPackage` to generate tests with knowledge of:
    - symbol dependencies
    - existing patterns
    - related tests
  - Runs tests afterwards, may loop with self-healing.

---

*(More workflows can be appended as they are identified: audit runs, docs generation, etc.)*

---

## 4. Subsystems

This section lists the core subsystems referenced by workflows.

### 4.1 Context & Knowledge

- **ContextService / ContextPackage**
  - Builds semantic bundles for the LLM:
    - symbols, imports, related functions, docstrings, nearby tests, etc.
  - Used by:
    - test generation
    - self-healing
    - (future) feature planners

- **Symbol Graph / Structural Index**
  - AST-based representation of functions, classes, modules.
  - Used for:
    - impact analysis
    - coverage mapping
    - refactor planning (future)

- **Vector Stores (Qdrant)**
  - Store embeddings for:
    - policies and constitution
    - patterns and docs (where configured)
    - possibly code context
  - Enable semantic retrieval of rules and knowledge.

---

### 4.2 Governance & Policies

- **Policies (YAML) in `.intent/charter/` / `.intent/policies/`**
  - Define:
    - allowed locations
    - naming rules
    - review requirements
    - audit expectations

- **Governance Engine / Audit Checks**
  - Apply policies to proposed changes:
    - environment checks
    - refactor checks
    - path/naming constraints
  - Produces **AuditFindings** with severities.

---

### 4.3 Execution & Orchestration

- **CognitiveService / LLM Router**
  - Selects and calls LLMs for:
    - code generation
    - self-healing
    - test generation
    - code review

- **Self-Healing Engines**
  - Use:
    - failure/violation context
    - ContextPackage
    - policies (via vector retrieval)
  - Attempt corrections and re-run tests.

- **CLI / Admin Commands**
  - `core-admin` entrypoints for:
    - context rebuild
    - inspection
    - coverage remediation
    - future A2 orchestration

---

### 4.4 Observability

- **Logger**
  - Standard logging for all components.
- **(Planned) Activity Log Helper**
  - A thin wrapper like `log_activity(workflow_id, event, status, details)` to give workflows a consistent activity story across subsystems.

---

## 5. Patterns & Guardrails

### 5.1 Workflow Patterns

- **Safe Mutating Workflow Pattern**
  - Any command that can mutate state must:
    - Support `dry-run` / simulation.
    - Default to **non-mutating** behavior.
    - Require an explicit flag (e.g. `--write`) to persist changes.
  - `inspect`-style commands are strictly read-only; no write flags allowed.

- **Inspect → Plan → Apply**
  - For impactful workflows:
    1. `inspect` – show what would happen.
    2. `plan` – generate explicit steps / diffs (could be combined with inspect).
    3. `apply` – execute changes only when explicitly requested.

---

### 5.2 Code & Architecture Patterns

- **Placement Patterns**
  - Features live under `src/features/...`
  - Services under `src/services/...`
  - Tests under `tests/...`
  - Governance logic under `mind/...` (or `.intent/` on the Mind side)

- **Naming & File Header Rules**
  - Functions: `snake_case`
  - Classes: `PascalCase`
  - Tests: `test_<thing>.py`
  - Files: first line is `# <repo-relative-path>`
  - Imports order:
    1. `from __future__ import annotations`
    2. stdlib
    3. third-party
    4. internal modules

- **Context Usage Pattern**
  - **New code MUST use `ContextPackage`** for non-trivial LLM interaction.
  - Legacy direct-context paths are considered migration debt.

---

### 5.3 Policy Usage Pattern

- Policies are:
  - Authored as YAML → `.intent/…`
  - Loaded and vectorized
  - Queried semantically by agents when deciding:
    - whether a change is allowed
    - how restrictive they must be
    - when to escalate or ask for human review

---

## 6. Dev Rituals (Developer-Facing)

### 6.1 `make dev-sync` – Canonical Consistency Ritual

**Goal:** bring CORE into a coherent, self-consistent state during development.

**Target behavior** (some parts may already exist, some are aspirational):

- Fix file headers & simple mechanical issues.
- Rebuild symbol graph / structural index.
- Sync / refresh vectorized policies.
- (Optionally) rebuild ContextPackage.
- Run a **light** audit/test cycle to ensure nothing is obviously broken.

**Pattern:**

- `make dev-sync` → show what will be done (dry-run / summary).
- `make dev-sync WRITE=1` or `make dev-sync-apply` → actually apply changes.

---

### 6.2 Migration Debt: Old Context vs ContextPackage

- Some modules still:
  - use older context access patterns
  - bypass `ContextPackage`
- These are **known migration debt**, not random design.

**Rules:**

- No new code should use the old context APIs.
- Migration is incremental:
  - when touching a legacy module, prefer upgrading it to ContextPackage.

---

## 7. Current Migration / Alignment Tasks

This section surfaces the “demons” explicitly so they are owned by the system, not just your head.

- **M1 – Workflow Visibility**
  - Keep this map updated as new workflows appear.
  - Long term: generate parts of this doc from `.intent/workflows/*.yaml`.

- **M2 – Unified Activity Logging**
  - Introduce `log_activity()` helper.
  - Gradually adopt it across major workflows (context rebuild, coverage remediation, self-healing).

- **M3 – Honest `dev-sync`**
  - Either:
    - rename current `dev-sync` to match its real scope, **or**
    - extend it to the full consistency ritual described in 6.1.

- **M4 – ContextPackage Migration**
  - Maintain a short list of modules still on the “old ways”.
  - Rule: no new code may be written on old paths.

---

## 8. How to Use This Map

- When adding a **new workflow**:
  - Give it an ID.
  - Classify `READ_ONLY` vs `READ_WRITE`.
  - Declare which subsystems it touches.
  - Declare if it follows `inspect → plan → apply`.

- When adding a **new agent / autonomy level**:
  - Place it in this map:
    - Which workflows does it orchestrate?
    - Which subsystems does it rely on?
    - Which patterns/guardrails does it enforce?

- When you feel “everything is ad-hoc”:
  - Come back here.
  - If something exists in code but not on this map:
    - It’s not governed yet → add it.
