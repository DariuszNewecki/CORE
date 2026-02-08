# CIM – Code Intelligence Monitor (Repo Census)

## 1. Purpose

CIM (Code Intelligence Monitor) provides **deterministic, evidence-based self‑inspection** of a code repository.

Its primary goal is to enable CORE to:

* Detect architectural and governance drift over time
* Compare the current state of the codebase against an explicit baseline
* Produce machine‑actionable findings suitable for CI, governance enforcement, and autonomous decision‑making

CIM is an **inspection surface**, not a refactoring engine and not a runtime monitor.

---

## 2. What CIM Measures (and What It Does Not)

### CIM Measures

* **Execution surfaces** (CLI entrypoints and executable boundaries)
* **Mutation surfaces** (filesystem, network, subprocess)
* **Write classification** (ephemeral vs production vs prohibited)
* **Lane distribution** (mind, body, will, shared, features, tests)
* **Change over time** (via snapshot comparison)

### CIM Does Not Measure

* Runtime behavior or performance
* Security vulnerabilities or exploitability
* Policy completeness or correctness
* Test coverage or semantic correctness

CIM answers *“What changed structurally?”*, not *“Is this code good?”*

---

## 3. Core Concepts

### Execution Surface

A bounded entrypoint through which code can be invoked (e.g. CLI commands). Execution surfaces define *where behavior starts*.

### Mutation Surface

Any operation capable of mutating state, including:

* Filesystem reads/writes
* Network connections
* Subprocess execution

Each mutation surface is classified by **type**, **operation**, **lane**, and **zone**.

### Lane

A logical architectural domain used by CORE for governance:

* `mind`
* `body`
* `will`
* `shared`
* `features`
* `tests`

Lane attribution is path‑based and deterministic.

### Write Classification

Filesystem writes are classified as:

* **Ephemeral** – temporary, non‑persistent artifacts
* **Production** – durable state or tracked artifacts
* **Prohibited** – writes to constitutionally protected zones

---

## 4. Determinism & Guarantees

CIM provides the following guarantees:

* Identical repository state + same tool version ⇒ identical census output
* Ordering, paths, and aggregation are normalized
* Snapshots are immutable once written
* Diffs are deterministic with respect to the chosen baseline

CIM does **not** attempt to infer intent or semantic meaning.

---

## 5. Commands & Usage

### Run Census Only

```
core-admin inspect repo-census
```

### Snapshot Current State

```
core-admin inspect repo-census --snapshot
```

### Diff Against Baseline

```
core-admin inspect repo-census --snapshot --diff <baseline>
```

### Diff Against Previous Snapshot

```
core-admin inspect repo-census --snapshot --diff --prev
```

---

## 6. Baselines

Baselines are **named, explicit anchors** used for comparison.

* Baselines map a name to a specific snapshot
* Baselines are stored under `var/cim/baselines.json`
* Typical baselines include release tags or pre‑refactor checkpoints

Baselines are never inferred implicitly.

---

## 7. Drift Detection & Policy Evaluation

CIM computes a structural diff (CIM‑Δ) between snapshots and evaluates it against policy thresholds.

Findings are classified by severity:

* BLOCK
* HIGH
* MEDIUM
* LOW

Each finding includes evidence and affected paths.

---

## 8. Exit Codes (Hard Contract)

Exit codes are a **stable interface** and MUST NOT be repurposed.

* `0` – No drift, no policy violations
* `2` – Drift detected, non‑blocking (warnings)
* `10` – Blocking constitutional violation (CI must fail)

These exit codes are designed for direct CI and automation use.

---

## 9. Storage & History Model

* CIM writes all artifacts under `var/cim/**`
* `var/cim/repo_census.json` represents the **latest run**
* `var/cim/history/` stores immutable snapshots
* `var/cim/history/` MAY be a symlink to external durable storage

This indirection is intentional and supported.

---

## 10. Example: Clean Run

```
✓ Census complete: /opt/dev/CORE/var/cim/repo_census.json
  Files scanned: 1645
  Execution surfaces: 14
  Mutation surfaces: 574
           INFO     INFO:body.services.cim.history:Saved snapshot: /opt/dev/CORE/var/cim/history/census_20260207_154403.json
✓ Snapshot saved: /opt/dev/CORE/var/cim/history/census_20260207_154403.json

Census Diff Summary
Baseline: v2.0.0

Execution surfaces: +0
Mutation surfaces: +0
  Ephemeral writes: +0
  Production writes: +0

Exit code: 0 (BLOCK: 0, HIGH: 0, MEDIUM: 0, LOW: 0)
```

A clean run indicates **no structural drift** relative to the baseline. It does not imply architectural perfection.

---

## 11. Example: Drift Detected

A run with detected drift will:

* Report non‑zero deltas
* Emit one or more findings
* Exit with code `2` or `10` depending on severity

This output is suitable for CI gating and autonomous proposal generation.

---

## 12. Non‑Goals & Explicit Limits

CIM explicitly does NOT:

* Modify code
* Suggest refactors
* Prove correctness
* Replace human architectural judgment

CIM provides **evidence**, not decisions.
