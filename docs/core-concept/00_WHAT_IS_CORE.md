# What Is CORE?

**CORE** is a *constitutional, self-governing AI development framework* designed to build software that can reason about itself, improve itself, and evolve safely under strict governance.

It does **not** try to replace developers. Instead, it provides a structured environment where:

* AI agents can propose and implement changes,
* the system can validate and audit those changes,
* humans maintain ultimate control through a constitutional process.

CORE is built for **precision**, **safety**, and **governed autonomy** — not uncontrolled code generation.

---

## 🧠 CORE’s Purpose

Traditional software development struggles with:

* Architectural drift
* Hidden dependencies
* Untested changes
* Knowledge loss over time
* Increasing maintenance overhead

CORE addresses these problems by:

1. **Embedding governance directly into the codebase** via the `.intent/` constitution.
2. **Linking all code to stable IDs, symbols, and capabilities**.
3. **Maintaining a Knowledge Graph** describing what the system *is*.
4. **Using AI agents to extend or modify code safely**.
5. **Enforcing rules through constitutional audits and policies**.
6. **Preventing unsafe or accidental changes**.

The result is a system that knows itself, protects itself, and evolves without losing structure.

---

## 🧬 CORE at a Glance

CORE is structured around three fundamental domains:

### **1. Mind — Governance & Constitution**

Location: `src/mind/`

The Mind defines and enforces the rules that govern the system:

* Policies
* Constitutional checks
* Safety rules
* Domain boundaries
* Audit pipeline

It ensures that all changes — human or AI — comply with the constitution.

---

### **2. Body — Execution Engine**

Location: `src/body/`, `src/features/`, `src/services/`

The Body performs all operational tasks:

* CLI (via `core-admin`)
* Crate lifecycle (creation, processing)
* Validation (Black, Ruff, Pytest)
* Context building
* Knowledge syncing
* Introspection, drift detection
* Self-healing and remediation

Everything that *runs* or *changes* the system lives here.

---

### **3. Will — Agents & Reasoning**

Location: `src/will/`

The Will hosts the AI components:

* Planner Agent
* Coder Agent
* Reviewer Agent
* Micro-Planner
* Cognitive Service
* Prompt Pipeline
* Validation Pipeline

These agents generate code, tests, and documentation — but **always under the constraints of the Mind**.

---

## 🔐 The Constitution (`.intent/`)

The `.intent/` directory is the *brainstem* of CORE.
It contains:

* Policies
* Domain rules
* Schema definitions
* Governance metadata
* Capability tags
* Intent bundles

All changes to `.intent/` must go through a **governed amendment process**:

1. A proposal is created.
2. A human signs it.
3. A canary instance applies the proposal in isolation.
4. A full audit runs.
5. Only if fully compliant is the change applied.

This gives CORE:

* **Safety**
* **Traceability**
* **Governable evolution**

---

## ⚙️ How CORE Works Day-to-Day

When you run something like:

```bash
poetry run core-admin develop feature "Add health endpoint"
```

CORE performs:

1. **Crate creation** — captures your intent.
2. **Context building** — gathers relevant files and knowledge.
3. **Autonomous development** — agents generate code & tests.
4. **Validation** — Black, Ruff, syntax, and test execution.
5. **Constitutional audit** — Mind enforces rules.
6. **Outcome** — crate accepted or rejected.

This provides **governed AI development**, not free-form generation.

---

## 🔍 What CORE Is *Not*

It is important to clarify misconceptions:

* ❌ CORE is not a generic LLM wrapper.
* ❌ CORE is not an auto-coder that dumps files into your repo.
* ❌ CORE is not a CI system.
* ❌ CORE is not a replacement for human oversight.

CORE is a **governed environment for safe AI automation**, with:

* Guardrails,
* Audits,
* Policies,
* Knowledge,
* Traceability.

---

## 🌱 Why CORE Exists

Because software systems decay.
Because humans leave companies.
Because undocumented decisions vanish.
Because AI without constraints is dangerous.

CORE provides:

* A single source of truth for intent.
* A persistent memory of system capabilities.
* Verified, autonomous assistance.
* Architecture that resists entropy.
* Governance that cannot be bypassed.

It ensures that systems become **more structured** over time, not less.

---

## 📎 Next Steps

Continue with:

* [Philosophy](01_PHILOSOPHY.md)
* [Architecture](02_ARCHITECTURE.md)
* [Governance](03_GOVERNANCE.md)

These will deepen your understanding of how CORE thinks, acts, and protects itself.

Welcome to the CORE project — where AI is powerful, but **governance is absolute**.
