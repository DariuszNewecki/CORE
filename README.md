# CORE

> **Where governance keeps AI accountable.**

[![Status: A2 — Governed](https://img.shields.io/badge/status-A2%20Governed-brightgreen.svg)](#-project-status-a2-governed-autonomy)
[![Governance: Constitutional](https://img.shields.io/badge/governance-Constitutional-blue.svg)](#-constitutional-governance)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://dariusznewecki.github.io/CORE/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![codecov](https://codecov.io/gh/DariuszNewecki/CORE/graph/badge.svg)](https://codecov.io/gh/DariuszNewecki/CORE)

CORE is a **constitutionally governed AI software system** that enables humans to plan, build, validate, and evolve software **without losing accountability, traceability, or control**.

It is designed for environments where **trust and governance matter as much as raw capability**, and where AI must be **powerful—but provably bounded** by human-authored constraints.

---

## See It in Action

[![asciicast](https://asciinema.org/a/S4tXkXUclYeTo6kEH1Z5UyUPE.svg)](https://asciinema.org/a/S4tXkXUclYeTo6kEH1Z5UyUPE)

[View full screen →](https://asciinema.org/a/S4tXkXUclYeTo6kEH1Z5UyUPE)

---

## Why CORE Exists

Modern systems fail less because code is hard to write, and more because **intent gets lost**:

* Architecture drifts from implementation
* Documentation rots
* Decisions lose their rationale
* Ownership becomes unclear
* No one can explain **why** the system behaves the way it does

AI accelerates this problem unless governance becomes **structural**.

CORE exists to prevent **unowned complexity**.
It does not replace humans. It replaces **technical gatekeeping, translation loss, and unmanaged drift**.

---

## 🏛️ Project Status: A2 Governed Autonomy (Operational)

CORE currently operates at **Level A2: Governed Autonomy**.

At this level, AI systems can generate and modify code **autonomously**, but **only within explicitly defined and continuously enforced governance boundaries**.

### Current Capabilities

* ✅ **A0 — Self-Awareness**: Knowledge graph operational (symbols, modules, relations)
* ✅ **A1 — Self-Healing**: Autonomous repairs (docstrings, headers, imports, formatting, compliance)
* ✅ **A2 — Governed Code Generation**: New code produced under constitutional validation (coverage-bounded)
* 🎯 **A3 — Strategic Refactoring**: Next frontier — multi-file architectural improvements

### Live Metrics (v2.0.0)

> Metrics reflect current enforcement scope and evolve as new rules and checkers are added.

**Governance**

* 32 constitutional policies documented
* 60+ rules actively enforced (~40% enforcement coverage; target: 50%+)
* 100% enforcement coverage for:

  * `agent_governance`
  * `dependency_injection`
  * `code_execution`

**Autonomy & Quality**

* Governed code generation success rate: **70–80%**
* Semantic placement accuracy: **100%**
* Knowledge graph: 500+ symbols, 60+ module anchors, 70+ policy chunks vectorized
* Test coverage: **~50%** (constitutional target: 75%)

---

## 🧠 What Is CORE?

CORE fixes drift by making **architecture machine-readable and enforceable**, rather than implicit, tribal, or documentation-bound.

It is built around a strict separation of concerns using the **Mind–Body–Will** model.

---

## 🧠 Mind — Constitution & State (`.intent/`, PostgreSQL)

The **Mind** is the authority layer.

* The **Constitution** defines immutable laws: principles, boundaries, schemas, and allowed dependencies
* The **database** stores symbols, capabilities, and relations as the single source of truth
* Semantic infrastructure enables AI reasoning about architecture and constraints

This is where **responsibility and authority live**.

---

## 🏗️ Body — Execution Machinery (`src/body/`, `src/services/`)

The **Body** is the deterministic execution layer.

* Auditing, filesystem operations, code parsing, and git control
* Central **Service Registry** for lifecycle and dependency management
* **Constitutional Auditor** enforcing rules and tracking violations
* 45+ specialized checkers validating compliance across the codebase

This is where rules are **enforced**, not negotiated.

---

## ⚡ Will — Reasoning Layer (`src/will/`)

The **Will** hosts AI agents that plan and propose actions.

* Agents can write, review, and improve code
* Every action is validated against constitutional rules
* Explicit **bounded autonomy lanes** define permissions and limits

This is where intelligence **works** — not where authority resides.

---

## Two Roles, One Authority

CORE enforces a strict role separation.

* **CORE-admin** defines governance, constraints, and evolution rules
* **End users** interact only through chat and requests within those constraints

Chat is **not** the capability surface.

**Governance is the capability surface.**

---

## 🏛️ Governance Architecture

CORE implements a layered governance model with progressive disclosure:

```
┌─────────────────────────────────────────────────────────────┐
│               CONSTITUTIONAL LAYER                          │
│        Principles — System-Level Governance                 │
│                                                             │
│  authority.yaml           → Who decides what                │
│  boundaries.yaml          → What is immutable               │
│  risk_classification.yaml → What needs oversight            │
│                                                             │
│  Paradigm: Foundational, coarse-grained, very stable         │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    POLICY LAYER                             │
│             Rules — Code-Level Enforcement                  │
│                                                             │
│  code_standards.yaml      → Enforced requirements            │
│  logging_standards.yaml   → Operational standards            │
│  data_governance.yaml     → Data & integrity rules           │
│  agent_governance.yaml    → Autonomy bounds                  │
│                                                             │
│  Paradigm: Fine-grained, implementation-specific, dynamic    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                  ENFORCEMENT LAYER                          │
│           Continuous Verification & Audit                   │
│                                                             │
│  Checkers × Rules → measurable enforcement coverage          │
│  Auto-discovery via flat rules array                         │
│  Progressive disclosure output                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 📚 Constitutional Documentation

CORE includes machine-readable governance artifacts aligned to industry-grade patterns:

| Document                    | Purpose                             | Status   |
| --------------------------- | ----------------------------------- | -------- |
| GLOBAL-DOCUMENT-META-SCHEMA | Universal metadata requirements     | ✅ Active |
| CONSTITUTION-STRUCTURE      | System-level governance principles  | 🆕 v2.0  |
| RULES-STRUCTURE             | Flat, enforceable rule definitions  | 🆕 v2.0  |
| POLICY-STRUCTURE            | Code-level policy standards         | 🆕 v2.0  |
| PATTERN-STRUCTURE           | Architectural & behavioral patterns | 🆕 v2.0  |

**Key innovation:** the **flat rules array** pattern — parser-friendly, extensible, and self-documenting.

---

## 🔒 Constitutional Governance

CORE’s claim is not that *AI can code*.

It is that:

> **AI can code safely when governance is explicit, enforced, and auditable.**

CORE ensures:

1. Human authority for critical decisions
2. Immutable constitutional boundaries
3. Continuous, machine-verifiable audit
4. Semantic understanding of constraints by agents
5. Progressive disclosure of results and violations

CORE does not prevent bad decisions.
It prevents **unowned decisions**.

---

## 🎯 Autonomy Ladder

```
A0 — Self-Awareness        ✅ Knowledge graph & symbol tracking
A1 — Self-Healing          ✅ Autonomous compliance repair
A2 — Governed Generation   ✅ Coverage-bounded code generation
A3 — Strategic Refactoring 🎯 Multi-file architectural change
A4 — Self-Replication     🔮 CORE generates CORE.NG from intent
```

**Current focus:** increase enforcement coverage beyond 50% and unlock A3 safely.

---

## 🚀 Getting Started (5-Minute Demo)

Run a minimal walkthrough: create an API, break a rule, and watch CORE catch it.

👉 **Run the Worked Example:** `docs/09_WORKED_EXAMPLE.md`

---

## 📖 Documentation Portal

🌐 [https://dariusznewecki.github.io/CORE/](https://dariusznewecki.github.io/CORE/)

* Foundations & philosophy
* Architecture (Mind / Body / Will)
* Governance and enforcement model
* Autonomy ladder and roadmap
* Contributing

---

## ⚙️ Installation & Quick Start

**Requirements:** Python 3.12+, Poetry, PostgreSQL, Qdrant (optional)

```bash
git clone https://github.com/DariuszNewecki/CORE.git
cd CORE
poetry install

cp .env.example .env
# add LLM provider keys

make db-setup
poetry run core-admin fix vector-sync --write
poetry run core-admin check audit
poetry run core-admin governance coverage
poetry run core-admin chat "create a CLI command that validates JSON files"
```

---

## 🛠️ Common Commands

| Command                        | Description                               |
| ------------------------------ | ----------------------------------------- |
| make check                     | Run lint, tests, and constitutional audit |
| core-admin fix all             | Autonomous compliance repair              |
| core-admin governance coverage | Show enforcement coverage                 |
| core-admin check audit         | Run full constitutional audit             |
| core-admin inspect status      | System health inspection                  |
| core-admin run develop         | Execute governed autonomous task          |

---

## 📄 License

Licensed under the **MIT License**. See `LICENSE`.
