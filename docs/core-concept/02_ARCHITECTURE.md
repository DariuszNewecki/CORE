# CORE System Architecture

CORE is an autonomous software engineer built on the **Mind–Body–Will cognitive architecture**.
This document reflects the **modern A2-ready architecture**, including the **Service Registry**, **Database-as-SSOT**, and **strict Dependency Injection**.

---

# 1. High-Level Design

```mermaid
graph TD
    Mind[Mind (.intent + DB)] -->|Governs| Will[Will (Agents)]
    Will -->|Orchestrates| Body[Body (Services & Tools)]
    Body -->|Executes| Filesystem
    Body -->|Updates| Mind
```

CORE maintains alignment between **intent**, **reasoning**, and **execution** through continuous governance.

---

## 1.1 The Architectural Trinity

### 🏛️ Mind — Governance, State & Knowledge

**Location:** `.intent/` + PostgreSQL

**Role:** Memory, governance, and global system state.

**Key Components:**

* **ConstitutionalAuditor** — enforces policies & architectural rules.
* **KnowledgeService** — interface to the Knowledge Graph.
* **PostgreSQL (SSOT)** — canonical store for symbols, capabilities, policies, secrets.

**Principle:**
**The Database is the Single Source of Truth (SSOT)** for system knowledge.
`.intent/` defines the *laws*. The DB reflects the *current state*.

---

### 🦾 Body — Deterministic Execution Layer

**Location:** `src/body/` + `src/services/` + `src/features/`

**Role:** Executes tasks deterministically.

**Key Components:**

* **ServiceRegistry** — singleton manager for infrastructure (LLMs, Git, Qdrant, DB, etc.).
* **ActionRegistry** — maps intent strings (e.g., "create_file") to executable actions.
* **FileHandler** — safe, staged file I/O using the Pending Writes pattern.
* **CLI (`core-admin`)** — governance entrypoint for audits, fixes, development, sync.

The Body **does not reason**.
It executes.

---

### 🧠 Will — Reasoning & Cognitive Layer

**Location:** `src/will/`

**Role:** Planning, reasoning, code generation, and self-correction.

**Key Components:**

* **CognitiveService** — LLM orchestration and provider abstraction.
* **PlannerAgent** — decomposes high-level goals.
* **Micro-Planner** — fine-grained reasoning.
* **CoderAgent** — writes, validates, and self-corrects code.
* **Reviewer & Deduction Agents** — ensure code quality and intent alignment.

The Will **must obey the Mind** and can act *only* through the Body.

---

# 2. Detailed Component View

## 2.1 Service Layer (Infrastructure)

All infrastructure adapters live in `src/services/` and are instantiated **exclusively** through the **ServiceRegistry**.

**Core Singleton Services:**

* **ConfigService** — loads runtime configuration (DB + env).
* **SecretsService** — handles encryption/decryption of API keys using Fernet.
* **QdrantService** — vector storage for embeddings & semantic search.
* **GitService** — wrapper for safe Git operations.
* **LLM Registry** — runtime model discovery & provider orchestration.
* **Database Session Manager** — async SQLAlchemy interface.

These are **never** instantiated directly elsewhere.

---

## 2.2 Dependency Injection Strategy

CORE enforces strict **Dependency Injection** to avoid "split-brain" infrastructure states.

**Key Rules:**

1. **The ServiceRegistry is the only place services are instantiated.**
2. **CoreContext** injects the registry into commands, agents, and feature pipelines.
3. Commands & agents request services **Just-In-Time (JIT)**.

**Example:**

```python
qdrant = await context.registry.get_qdrant_service()
```

**Outcome:**
No duplicates, no stale connections, no conflicting resources.

---

## 2.3 The Knowledge Loop

CORE maintains self-awareness via a continuous closed-loop process:

1. **Introspection** — `SymbolScanner` parses every Python file in `src/`.
2. **Sync** — `KnowledgeService` updates the `core.symbols` table.
3. **Vectorize** — embeddings are generated and written to Qdrant.
4. **Retrieval** — agents query semantic memory to:

   * find patterns,
   * reuse code,
   * detect inconsistencies,
   * generate governed fixes.

This pipeline enables autonomous reasoning grounded in the real system structure.

---

# 3. Governance Model

All system evolution must follow the **Constitutional Workflow**.

## 3.1 Proposal Phase

Human or agent creates a **proposal crate**:

* describes intent,
* includes planned modifications,
* contains initial code generation.

## 3.2 Audit Phase

The **ConstitutionalAuditor** validates:

* policies,
* dependencies,
* architectural boundaries,
* capabilities & symbol metadata,
* missing tests,
* duplication,
* security rules.

If any audit fails → crate rejected.

## 3.3 Canary Phase

The system applies changes to a **temporary directory** and:

* runs Black, Ruff, and pytest,
* performs introspection & knowledge sync simulation.

## 3.4 Commitment Phase

Only if **all** checks pass:

* changes are written to disk,
* knowledge is updated,
* the system evolves safely.

Nothing bypasses this process.

---

# 4. Mind–Body–Will (Full Context)

## 4.1 Mind — `.intent/`

Holds:

* principles,
* policies,
* governance contracts,
* schemas,
* constitutional rules,
* runtime requirements.

It defines what CORE **is allowed** to be.

## 4.2 Body — `src/`

Implements:

* deterministic tooling,
* feature domains,
* validation pipeline,
* operational workflows.

## 4.3 Will — `src/will/`

Implements:

* planning,
* reasoning,
* generation,
* alignment,
* self-correction.

The Will cannot write code outside of governed pathways.

---

# 5. Why This Architecture Works

CORE maintains:

* **alignment** between intent and implementation,
* **controlled reasoning** via Mind-enforced guardrails,
* **auditable evolution** via the crate model,
* **explicit knowledge** through PostgreSQL + Qdrant,
* **safe change paths** through constitutional audits.

The Mind–Body–Will model is the foundation of safe autonomous development.

---

# 6. Next Steps

Continue with:

* **Governance Model (`03_GOVERNANCE.md`)**
* **Philosophy (`01_PHILOSOPHY.md`)**
* **Developer Cheat Sheet** — concise atomic references

This architecture enables CORE to function as a **governed, self-improving software engineer**.
