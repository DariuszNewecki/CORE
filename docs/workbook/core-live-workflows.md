# CORE Live Workflow System — DB‑First Architecture

## 1. Purpose

This document defines the **CORE Live Workflow System**: how workflows are modeled, stored, governed, executed, and evolved in a system targeting **A‑3 autonomy**.

At A‑3, workflows are no longer static configuration artifacts. They are **live operational assets** that:

* can evolve at runtime,
* may be proposed or drafted by CORE itself,
* require human interaction for activation,
* must remain auditable, reproducible, and constitutionally safe.

This document deliberately separates **law (Constitution)** from **operations (Workflows)**.

---

## 2. Authority Model (Non‑Negotiable)

CORE operates under a two‑tier authority model.

### 2.1 Constitution (Law)

* Source of truth for governance
* Read‑only at runtime
* Defines:

  * who may change workflows
  * which workflow types are allowed
  * what capabilities workflows may invoke
  * which approvals are required

The Constitution **governs workflows**, but workflows must never modify the Constitution.

### 2.2 Workflows (Operations)

* Live, mutable, versioned
* Executed by SRC
* Stored in the database
* Can be proposed by CORE or humans
* Can only be activated through governed approval paths

**Invariant:** workflows must never become a backdoor for constitutional change.

---

## 3. Why Workflows Live in the Database

For A‑3 autonomy, workflows must support:

* transactional updates
* concurrent access
* version binding per execution
* auditable history
* human approval trails

Filesystem‑based workflows fail these requirements.

**Therefore: the database is the authoritative source of truth for workflows.**

---

## 4. Core Design Invariants

The following invariants MUST hold at all times:

1. **Workflows are versioned, never edited**
2. **Workflow versions are immutable**
3. **A workflow run binds to exactly one version**
4. **Activation is separate from definition**
5. **Mid‑run mutation is impossible**
6. **Rollback is first‑class and governed**
7. **All workflow changes are auditable**

---

## 5. Database Model (Minimal, A‑3‑Safe)

### 5.1 Workflows Registry

Holds the stable identity and metadata.

* `workflows`

  * `id`
  * `name`
  * `description`
  * `owner_role`
  * `domain_tags`
  * `created_at`
  * `created_by`

---

### 5.2 Workflow Versions (Immutable)

Each change produces a new version.

* `workflow_versions`

  * `workflow_id`
  * `version`
  * `definition` (canonical text)
  * `definition_hash`
  * `created_at`
  * `created_by`
  * `validation_status`
  * `policy_gate_status`

Once written, a version **must never change**.

---

### 5.3 Workflow State (Activation Pointer)

Controls which version is active.

* `workflow_state`

  * `workflow_id`
  * `active_version`
  * `status` (draft / proposed / approved / active / deprecated / retired)
  * `updated_at`
  * `updated_by`

---

### 5.4 Change Control (Human Interaction)

Tracks proposals, rationale, and approvals.

* `workflow_change_requests`

  * `id`
  * `workflow_id`
  * `from_version`
  * `to_version`
  * `rationale`
  * `diff_summary`
  * `requested_by`
  * `approval_status`
  * `approved_by`
  * `approved_at`

---

### 5.5 Workflow Runs (Execution Binding)

Records every execution with exact version lineage.

* `workflow_runs`

  * `run_id`
  * `workflow_id`
  * `bound_version`
  * `trigger` (manual / scheduled / agent / system)
  * `status`
  * `trace_id`
  * timestamps

---

## 6. Workflow Definition Format

### 6.1 Authoring vs Execution

* **Authoring format:** Canonical YAML (stored as text in DB)
* **Execution format:** Compiled internal Workflow IR

YAML is used because:

* humans can review diffs
* CORE can propose patches deterministically
* schemas can be strictly enforced

SRC **never executes raw YAML** — only compiled IR.

---

### 6.2 Allowed Workflow Constructs

Workflow definitions may reference only:

* registered atomic actions
* capability calls (reason / generate / embed)
* explicit decision points
* human approval gates

Workflows may NOT:

* execute arbitrary code
* call providers directly
* mutate the Constitution
* bypass SRC

---

## 7. Workflow Lifecycle

Every workflow version follows this lifecycle:

1. **Draft** – definition exists, not validated
2. **Proposed** – change request created
3. **Validated** – schema + policy checks passed
4. **Approved** – human approval recorded
5. **Active** – version selected for execution
6. **Deprecated** – superseded, no new runs
7. **Retired** – no longer executable

Lifecycle transitions are governed by Constitution rules.

---

## 8. Governance Gates (Critical for A‑3)

### 8.1 Proposal Gate

* CORE or human submits a new version
* Rationale is mandatory

### 8.2 Validation Gate

* Schema validation
* Policy evaluation
* Safety checks (no forbidden actions, no unbounded execution)

### 8.3 Human Approval Gate

* Required unless explicitly exempted by Constitution
* Approval is recorded and immutable

### 8.4 Activation Gate

* SRC updates active version pointer
* Only allowed after all required approvals

---

## 9. Runtime Semantics

* Each workflow run binds to a **specific version**
* Active version changes do NOT affect running executions
* Execution traces always reference the bound version
* Rollback changes only affect future runs

This guarantees reproducibility and auditability.

---

## 10. Workflow Registry Interface

SRC accesses workflows exclusively through a governed interface.

### Read Operations

* `get_active(workflow_id)`
* `get_version(workflow_id, version)`
* `list_active()`

### Write Operations (Governed)

* `propose(workflow_id, definition, rationale)`
* `validate(version_id)`
* `request_approval(change_request_id)`
* `activate(workflow_id, version)`
* `rollback(workflow_id, version)`

Direct DB mutation outside this interface is forbidden.

---

## 11. Relationship to SRC

SRC:

* loads workflow IR from the registry
* enforces constitutional constraints
* executes workflows deterministically
* records runs and traces

SRC is the **only executor**. Workflows do not execute themselves.

---

## 12. Why This Enables A‑3 Autonomy Safely

This model allows CORE to:

* suggest and draft workflow improvements
* validate them automatically
* request human approval
* activate changes safely

While preserving:

* constitutional authority
* auditability
* reproducibility
* human control over operational change

---

## 13. Final Invariants (Freeze These)

1. Constitution governs workflows
2. Workflows are live, versioned DB assets
3. Workflow versions are immutable
4. Runs bind to versions
5. Activation is governed
6. SRC is the sole executor
7. CORE may propose, but not silently activate

With these invariants enforced, CORE can progress to A‑3 autonomy without losing control.
