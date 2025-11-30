# CORE — The Self‑Improving System Architect

> **Where Intelligence Lives.**

[![Status: A2 Achieved](https://img.shields.io/badge/status-A2%20Achieved-brightgreen.svg)](#-project-status)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://dariusznewecki.github.io/CORE/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![codecov](https://codecov.io/gh/DariuszNewecki/CORE/graph/badge.svg)](https://codecov.io/gh/DariuszNewecki/CORE)

CORE is a **self‑governing, constitutionally aligned AI development system** capable of planning, writing, validating, and evolving software **autonomously and safely**. It is designed for environments where **trust, traceability, and governance matter as much as raw capability**.

## See It In Action

<script src="https://asciinema.org/a/S4tXkXUclYeTo6kEH1Z5UyUPE.js" id="asciicast-S4tXkXUclYeTo6kEH1Z5UyUPE" async></script>

[View full screen](https://asciinema.org/a/S4tXkXUclYeTo6kEH1Z5UyUPE)

---

## 🏛️ Project Status: A2 Autonomy Achieved

**CORE has achieved Level 2 Autonomy (A2): Autonomous Code Generation**

### Current Capabilities

* ✅ **A0 (Self-Awareness)**: 513 symbols vectorized, 66 module anchors, knowledge graph operational
* ✅ **A1 (Self-Healing)**: Automatic docstrings, headers, imports, formatting, constitutional compliance
* ✅ **A2 (Code Generation)**: 70-80% success rate on autonomous code generation with constitutional governance
* 🎯 **A3 (Strategic Refactoring)**: Next frontier - multi-file architectural improvements

### Live Metrics (v2.0.0)

* **Autonomous Code Generation**: 70-80% success rate (up from 0%)
* **Semantic Placement Accuracy**: 100% (up from 45%)
* **Knowledge Graph**: 513 symbols, 66 module anchors, 48 policy chunks
* **Test Coverage**: 48-51% (target: 75%)
* **Constitutional Compliance**: Active monitoring with autonomous remediation

### Production-Grade Architecture

* Robust **Service Registry** with strict dependency injection
* PostgreSQL-backed **Knowledge Graph** (Single Source of Truth)
* **Constitutional Audit System** preventing AI agents from "going off the rails"
* Fully operational **self-governance loop**: Introspection → Validation → Self-Healing

---

## 🧠 What Is CORE?

Traditional systems drift: architecture diverges from the implementation; design documents rot; no one has the full picture.

CORE fixes this by making **the architecture machine‑readable and enforceable**.

It is built on the **Mind–Body–Will** model:

### 🧠 Mind — The Constitution & State (`.intent/`, PostgreSQL)

* The **Constitution** defines immutable laws: structure, policies, schemas, allowed dependencies.
* The **Database** stores every symbol, capability, and relation as the **Single Source of Truth**.
* **Semantic Infrastructure**: Policies, symbols, and architectural context vectorized for AI reasoning.

### 🏗️ Body — The Machinery (`src/body/`, `src/services/`)

* Provides deterministic tools: auditing, filesystem operations, code parsing, git control.
* A centralized **Service Registry** ensures clean lifecycle management and singleton resources.
* **Constitutional Auditor** enforces governance rules and tracks violations.

### ⚡ Will — The Reasoning Layer (`src/will/`)

* AI Agents that plan, write, and review code autonomously.
* Agents never act freely: **every action is pre‑validated** against the Constitution.
* **Context-Aware Code Generation**: Rich semantic context enables accurate, policy-compliant code.

This creates a system that can **understand itself**, detect deviations, and evolve safely.

---

## 🎯 The Autonomy Ladder

CORE progresses through defined autonomy levels:

```
A0: Self-Awareness          ✅ Knowledge graph, symbol vectorization
A1: Self-Healing            ✅ Autonomous fixes for drift, formatting, compliance
A2: Code Generation         ✅ Create new features with constitutional governance
A3: Strategic Refactoring   🎯 Multi-file architectural improvements
A4: Self-Replication        🔮 Write CORE.NG from scratch based on functionality
```

---

## 🚀 Getting Started (5‑Minute Demo)

Run a minimal walkthrough: create an API, break a rule, and watch CORE catch it.

👉 **[Run the Worked Example](docs/09_WORKED_EXAMPLE.md)**

---

## 📖 Documentation Portal

🌐 **[https://dariusznewecki.github.io/CORE/](https://dariusznewecki.github.io/CORE/)**

* **What is CORE?** – Foundations & philosophy
* **Architecture** – Mind/Body/Will, Service Registry, Knowledge Graph
* **Governance** – How CORE enforces constitutional rules
* **Autonomy Ladder** – From self-awareness to self-replication
* **Roadmap** – Towards A3, A4, and full autonomous delivery
* **Contributing** – How to collaborate

---

## ⚙️ Installation & Quick Start

**Requirements:** Python 3.12+, Poetry

```bash
# Clone and install
git clone https://github.com/DariuszNewecki/CORE.git
cd CORE
poetry install

# Prepare config
cp .env.example .env
# Add LLM keys (OpenAI, Anthropic, Ollama)

# 1. Build Knowledge Graph
poetry run core-admin fix vector-sync --write

# 2. Run full audit
poetry run core-admin check audit

# 3. Try autonomous code generation
poetry run core-admin chat "create a CLI command that validates JSON files"
```

---

## 🛠️ Common Commands

| Command                     | Description                                      |
| --------------------------- | ------------------------------------------------ |
| `make check`                | Run Lint, Test, Audit (full governance pipeline) |
| `core-admin fix all`        | Autonomous repair: headers, metadata, formatting |
| `core-admin inspect status` | Check DB, migrations, and registry health        |
| `core-admin run develop`    | Execute autonomous, governed coding task         |

---

## 🔒 Constitutional Governance

CORE's key innovation is **constitutional AI governance**:

* All policies stored as human-authored YAML in `.intent/charter/policies/`
* AI agents operate within defined "autonomy lanes" with explicit permissions
* Cryptographic signing for constitutional amendments (quorum-based approval)
* Continuous audit system catches and remediates violations
* Semantic policy vectorization enables AI understanding of governance rules

**Result**: AI agents that are powerful yet provably bounded by human-defined constraints.

---

## 📊 Success Metrics

From initial implementation to A2 achievement:

* Code generation success: **0% → 70-80%**
* Semantic placement accuracy: **45% → 100%**
* Test success rate: **0% → 70-80%**
* Knowledge graph symbols: **0 → 513**
* Policy chunks vectorized: **0 → 48**

All improvements driven by constitutional governance and semantic infrastructure.

---

## 📄 License

Licensed under the **MIT License**. See `LICENSE`.
