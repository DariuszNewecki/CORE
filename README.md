# CORE — The Last Programmer You Will Ever Need

> **Where Governance Lives. Where Intelligence Is Constrained.**

[![Status: A2 Achieved](https://img.shields.io/badge/status-A2%20Achieved-brightgreen.svg)](#-project-status-a2-autonomy-achieved)
[![Constitutional Governance](https://img.shields.io/badge/governance-Constitutional-blue.svg)](#-constitutional-governance)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://dariusznewecki.github.io/CORE/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![codecov](https://codecov.io/gh/DariuszNewecki/CORE/graph/badge.svg)](https://codecov.io/gh/DariuszNewecki/CORE)

CORE is a **constitutionally governed AI development system** that enables humans to plan, build, validate, and evolve software **without losing accountability, traceability, or control**.

It is designed for environments where **trust and governance matter as much as raw capability**, and where AI must be **powerful—but provably bounded** by human-authored constraints.

---

## See It In Action

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

## 🏛️ Project Status: A2 Autonomy Achieved

**CORE has achieved Level 2 Autonomy (A2): Governed Code Generation**

### Current Capabilities

* ✅ **A0 (Self-Awareness)**: knowledge graph operational (symbols + module anchors)
* ✅ **A1 (Self-Healing)**: automatic repairs (docstrings, headers, imports, formatting, compliance)
* ✅ **A2 (Governed Code Generation)**: autonomous code generation under constitutional governance
* 🎯 **A3 (Strategic Refactoring)**: next frontier — multi-file architectural improvements

### Live Metrics (v2.0.0)

**Governance:**

* 32 constitutional policies documented
* 60+ rules actively enforced (40.5% enforcement coverage; targeting 50%+)
* 100% enforcement: `agent_governance`, `dependency_injection`, `code_execution`

**Autonomy:**

* Code generation success: **70–80%**
* Semantic placement accuracy: **100%**
* Knowledge graph: 513 symbols, 66 module anchors, 73 policy chunks vectorized
* Test coverage: **48–51%** (constitutional target: 75%)

---

## 🧠 What Is CORE?

CORE fixes drift by making **architecture machine-readable and enforceable**.

It is built on the **Mind–Body–Will** model:

### 🧠 Mind — The Constitution & State (`.intent/`, PostgreSQL)

* **Constitution** defines immutable laws: structure, policies, schemas, allowed dependencies
* **Database** stores symbols, capabilities, and relations as the **Single Source of Truth**
* **Semantic infrastructure** enables AI reasoning about architecture and constraints

This is where **responsibility lives**.

### 🏗️ Body — The Machinery (`src/body/`, `src/services/`)

* Deterministic tooling: auditing, filesystem ops, code parsing, git control
* Central **Service Registry** for lifecycle management and singleton resources
* **Constitutional Auditor** enforces governance rules and tracks violations
* 45 specialized checkers validate compliance across the codebase

This is where rules are **enforced**.

### ⚡ Will — The Reasoning Layer (`src/will/`)

* AI agents that plan, write, review, and improve code
* Agents never act freely: **every action is validated** against the Constitution
* “Bounded autonomy lanes” define explicit permissions and limits

This is where intelligence **works**, not decides.

---

## Two Roles, One Authority

CORE is designed around role separation.

* **CORE-admin**: defines governance (via policy layer / future Policy Editor), owns constraints and evolution
* **End-User**: chats only; can request actions **only within governance**

Chat is not the capability surface.
**Governance is the capability surface.**

---

## 🏛️ Governance Architecture

CORE implements a governance stack with progressive disclosure:

```
┌─────────────────────────────────────────────────────────────┐
│              CONSTITUTIONAL LAYER                           │
│        (Principles - System-Level Governance)               │
│                                                             │
│  authority.yaml           → Who decides what                │
│  boundaries.yaml          → What’s immutable                │
│  risk_classification.yaml → What needs oversight            │
│                                                             │
│  Paradigm: Foundational, coarse-grained, very stable        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                  POLICY LAYER                               │
│           (Rules - Code-Level Enforcement)                  │
│                                                             │
│  code_standards.yaml      → Enforced requirements           │
│  logging_standards.yaml   → Operational standards           │
│  data_governance.yaml     → Data & integrity rules          │
│  agent_governance.yaml    → Autonomy bounds                 │
│                                                             │
│  Paradigm: Fine-grained, implementation-specific, dynamic    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────────┐
│              ENFORCEMENT LAYER                              │
│        (Checkers - Continuous Verification)                 │
│                                                             │
│  Checkers × Rules = measurable enforcement coverage          │
│  Auto-discovery via flat rules array                         │
│  Progressive disclosure output (kubectl/git/docker pattern)  │
└─────────────────────────────────────────────────────────────┘
```

**Relationship:** Principles set boundaries → Policies implement boundaries → Checkers verify compliance.

---

## 📚 Constitutional Documentation

CORE includes governance documentation aligned to industry-grade patterns:

| Document                                                                                          | Purpose                                                          | Status   |
| ------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | -------- |
| **[GLOBAL-DOCUMENT-META-SCHEMA](/.intent/charter/constitution/GLOBAL-DOCUMENT-META-SCHEMA.yaml)** | Universal header requirements for all `.intent` documents        | ✅ Active |
| **[CONSTITUTION-STRUCTURE](/.intent/charter/constitution/CONSTITUTION-STRUCTURE.yaml)**           | Principles-based system governance (authority, boundaries, risk) | 🆕 v2.0  |
| **[RULES-STRUCTURE](/.intent/charter/constitution/RULES-STRUCTURE.yaml)**                         | Universal standard for enforceable rules (flat array pattern)    | 🆕 v2.0  |
| **[POLICY-STRUCTURE](/.intent/charter/constitution/POLICY-STRUCTURE.yaml)**                       | Standards for code-level policies                                | 🆕 v2.0  |
| **[PATTERN-STRUCTURE](/.intent/charter/constitution/PATTERN-STRUCTURE.yaml)**                     | Standards for architectural and behavioral patterns              | 🆕 v2.0  |

**Key innovation:** the **flat rules array** pattern.

* Parser-friendly (no category-driven breakage)
* Extensible (new categories without code changes)
* Self-documenting (categories visible in each rule)

---

## 🔒 Constitutional Governance

CORE’s key claim is not “AI can code.”
It is:

> **AI can code safely when governance is explicit, enforced, and auditable.**

CORE enforces:

1. **Human authority** for critical operations
2. **Immutable boundaries** (Constitution cannot be modified by agents)
3. **Continuous audit** against policies and principles
4. **Semantic understanding of constraints** (agents reason about rules)
5. **Progressive disclosure** (actionable outputs first)

CORE does not prevent bad decisions.
It prevents **unowned decisions**.

---

## 🎯 The Autonomy Ladder

```
A0: Self-Awareness          ✅ Knowledge graph, symbol vectorization
A1: Self-Healing            ✅ Autonomous fixes for drift, compliance
A2: Governed Code Generation ✅ New features under constitutional governance
A3: Strategic Refactoring   🎯 Multi-file architectural improvements
A4: Self-Replication        🔮 CORE writes CORE.NG from declared intent
```

**Current focus:** reach 50%+ enforcement coverage and unlock A3 safely.

---

## 🚀 Getting Started (5‑Minute Demo)

Run a minimal walkthrough: create an API, break a rule, and watch CORE catch it.

👉 **[Run the Worked Example](docs/09_WORKED_EXAMPLE.md)**

---

## 📖 Documentation Portal

🌐 **[https://dariusznewecki.github.io/CORE/](https://dariusznewecki.github.io/CORE/)**

* Foundations & philosophy
* Architecture (Mind/Body/Will)
* Governance and enforcement model
* Autonomy ladder and roadmap
* Contributing

---

## ⚙️ Installation & Quick Start

**Requirements:** Python 3.12+, Poetry, PostgreSQL, Qdrant (optional)

```bash
# Clone and install
git clone https://github.com/DariuszNewecki/CORE.git
cd CORE
poetry install

# Prepare config
cp .env.example .env
# Add LLM keys (OpenAI, Anthropic, Ollama)

# 1. Initialize databases
make db-setup

# 2. Build Knowledge Graph
poetry run core-admin fix vector-sync --write

# 3. Run full constitutional audit
poetry run core-admin check audit

# 4. Check governance coverage
poetry run core-admin governance coverage --format hierarchical

# 5. Try autonomous code generation
poetry run core-admin chat "create a CLI command that validates JSON files"
```

---

## 🛠️ Common Commands

| Command                          | Description                                        |
| -------------------------------- | -------------------------------------------------- |
| `make check`                     | Run lint, tests, and constitutional audit          |
| `core-admin fix all`             | Autonomous repair: headers, metadata, formatting   |
| `core-admin governance coverage` | Show enforcement coverage (progressive disclosure) |
| `core-admin check audit`         | Run constitutional compliance audit                |
| `core-admin inspect status`      | Check DB, migrations, and registry health          |
| `core-admin run develop`         | Execute an autonomous governed coding task         |

---

## 📄 License

Licensed under the **MIT License**. See `LICENSE`.
