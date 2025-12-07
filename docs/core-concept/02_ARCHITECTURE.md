# CORE System Architecture

This document defines the **authoritative, A2‑ready architectural model** of CORE, based on the canonical **Mind–Body–Will cognitive framework**. It is written in a formal and enduring style, suitable for inclusion in CORE's doctrinal documentation.

The architecture described here reflects:

* **Service Registry–based infrastructure management**
* **Database as Single Source of Truth (SSOT)**
* **Strict Dependency Injection (DI)**
* **Governed execution and reasoning pathways**

---

# 1. High‑Level Design

```mermaid
graph TD
    Mind[Mind (.intent + DB)] -->|Governs| Will[Will (Agents)]
    Will -->|Orchestrates| Body[Body (Services & Tools)]
    Body -->|Executes| Filesystem
    Body -->|Updates| Mind
```

CORE maintains alignment between **intent**, **reasoning**, and **execution** through continuous governance. Every system evolution flows from the Mind, through the Will, into the Body, and finally returns updated knowledge back to the Mind.

---

# 1.1 The Architectural Trinity

## 🏛️ Mind — Governance, State, and Knowledge

**Location:** `.intent/` + PostgreSQL

**Purpose:** Define what CORE *is allowed* to be. The Mind holds the immutable laws and the mutable state of the system.

**Key Components:**

* **ConstitutionalAuditor** — enforces rules, prevents drift, blocks unsafe evolution.
* **KnowledgeService** — interface to the Knowledge Graph and symbol metadata.
* **PostgreSQL (SSOT)** — canonical store for all system knowledge.

**Principle:**

> **The Database is the Single Source of Truth (SSOT).**

`.intent/` defines the *law*. The database captures the *world as it currently exists*.

---

## 🦾 Body — Deterministic Execution Layer

**Location:** `src/body/`, `src/services/`, `src/features/`

**Purpose:** Execute work deterministically, predictably, and without agency.

**Key Components:**

* **ServiceRegistry** — the sole authority for constructing and providing infrastructure services.
* **ActionRegistry** — maps intent identifiers to executable atomic actions.
* **FileHandler** — safe file I/O using staging and validation.
* **core-admin CLI** — governance entrypoint for audits, diagnostics, fixes, development cycles.

The Body does **not** reason.
It simply executes instructions under strict governance.

---

## 🧠 Will — Cognitive and Reasoning Layer

**Location:** `src/will/`

**Purpose:** Planning, decomposition, reasoning, generation, validation, and self‑correction.
The Will is the only layer permitted to use LLMs.

**Key Components:**

* **CognitiveService** — orchestrates LLM calls and selects providers.
* **PlannerAgent** — decomposes goals into executable plans.
* **Micro‑Planner** — performs fine‑grained reasoning loops.
* **CoderAgent** — generates and validates code changes.
* **Reviewer & Deduction Agents** — ensure coherence, correctness, and alignment.

**Constraint:**

> The Will must obey the Mind and act only through the Body.

---

# 2. Detailed Component Model

## 2.1 Infrastructure Services

All infrastructure adapters (LLMs, DB, Qdrant, Git, Secrets, Config, etc.) live in `src/services/` and are instantiated **exclusively** through the **ServiceRegistry**.

**Core Services:**

* **ConfigService** — loads and validates runtime configuration.
* **SecretsService** — manages encrypted secrets (Fernet‑based).
* **QdrantService** — embedding storage and semantic search.
* **GitService** — safe Git operations under governance.
* **LLM Provider Registry** — runtime model discovery and orchestration.
* **Database Session Manager** — async SQLAlchemy engine and session factory.

**Rule:** No service may be instantiated outside the registry.

---

## 2.2 Dependency Injection Strategy

CORE enforces strict DI to maintain global coherence and avoid duplicated infrastructure instances.

### Rules

1. **The ServiceRegistry constructs all services.**
2. **CoreContext delivers these services to commands, features, and agents.**
3. **Consumers request services Just‑In‑Time (JIT).**

**Example:**

```python
qdrant = await context.registry.get_qdrant_service()
```

Outcome: no split‑brain infrastructure, no conflicting engines, no stale connections.

---

## 2.3 The Knowledge Loop

CORE maintains system self‑awareness using a closed knowledge loop:

1. **Introspection** — `SymbolScanner` analyzes Python modules.
2. **Sync** — symbols, capabilities, and metadata are written to PostgreSQL.
3. **Vectorization** — embeddings stored in Qdrant enable semantic reasoning.
4. **Retrieval & Use** — agents leverage semantic memory to:

   * detect inconsistencies,
   * perform reuse analysis,
   * guide refactoring,
   * generate governed code fixes.

This loop grounds reasoning in the system’s actual structure.

---

# 3. Governance Model

CORE evolves through a governed workflow enforced by constitutional law.

## 3.1 Proposal Phase

A human or agent submits a **proposal crate** containing:

* description of change intent,
* planned modifications,
* initial generated code.

## 3.2 Audit Phase

The **ConstitutionalAuditor** validates:

* policy compliance,
* domain boundaries,
* capability metadata,
* potential drift or duplication,
* missing tests,
* safety and structure of changes.

Crates failing audit are rejected immediately.

## 3.3 Canary Phase

Changes are applied to a temporary environment and subjected to:

* formatting checks (Black, Ruff),
* full pytest suite,
* knowledge sync simulation.

## 3.4 Commitment Phase

Only after *all* checks succeed:

* changes are written to disk,
* introspection updates system knowledge,
* the system’s state evolves safely.

Nothing bypasses this workflow.

---

# 4. Mind–Body–Will in Context

## 4.1 Mind — `.intent/`

Defines:

* constitutional principles,
* policies,
* schemas,
* governance contracts,
* runtime constraints.

This layer defines what CORE is **allowed** to be.

---

## 4.2 Body — `src/`

Implements:

* deterministic services,
* operational workflows,
* checks,
* audits,
* feature domains.

This layer performs the work.

---

## 4.3 Will — `src/will/`

Implements:

* reasoning,
* planning,
* code generation,
* validation,
* self‑correction.

The Will cannot modify the system except through governed channels enforced by the Mind.

---

# 5. Why This Architecture Works

CORE achieves:

* **Persistent alignment** between intent and implementation,
* **Governed reasoning** via constitutional guardrails,
* **Auditable evolution** using crate‑based change management,
* **Explicit knowledge** stored in DB + vector memory,
* **Safe self‑improvement** through closed governance loops.

The Mind–Body–Will model forms the foundation for **safe, autonomous code evolution**.

---

# 6. Next Steps

Recommended readings:

* **Governance Model (`03_GOVERNANCE.md`)**
* **Philosophy (`01_PHILOSOPHY.md`)**
* **Developer Cheat Sheet** (compact operational reference)

This architecture defines CORE’s evolution from A2‑level autonomy toward governed, self‑maintaining development.
