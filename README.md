# CORE — The Self‑Improving System Architect

> **Where Intelligence Lives.**

[![Status: Alpha (A2-Ready)](https://img.shields.io/badge/status-Alpha%20\(A2--Ready\)-green.svg)](#-project-status)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://dariusznewecki.github.io/CORE/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![codecov](https://codecov.io/gh/DariuszNewecki/CORE/graph/badge.svg)](https://codecov.io/gh/DariuszNewecki/CORE)

CORE is a **self‑governing, constitutionally aligned AI development system** capable of planning, writing, validating, and evolving software **autonomously and safely**. It is designed for environments where **trust, traceability, and governance matter as much as raw capability**.

---

## 🏛️ Project Status: Alpha (A2‑Ready)

CORE has moved beyond architectural experimentation and now provides:

* A robust, production‑grade **Service Registry** architecture
* Strict **dependency injection** across all system layers
* A fully synchronized **Knowledge Graph** (database‑backed SSOT)
* Stable **self‑governance loop**

The internal feedback cycle is fully operational:

1. **Introspection** – CORE parses its codebase and updates the symbolic graph in PostgreSQL.
2. **Validation** – The `ConstitutionalAuditor` enforces all architectural & governance rules.
3. **Self‑Healing** – Agents automatically fix documentation drift, formatting, and structural violations.

The next frontier is **A2 (Governed Code Generation)**: controlled, auditable creation of new features.

---

## 🧠 What Is CORE?

Traditional systems drift: architecture diverges from the implementation; design documents rot; no one has the full picture.

CORE fixes this by making **the architecture machine‑readable and enforceable**.

It is built on the **Mind–Body–Will** model:

### 🧠 Mind — The Constitution & State (`.intent/`, PostgreSQL)

* The **Constitution** defines immutable laws: structure, policies, schemas, allowed dependencies.
* The **Database** stores every symbol, capability, and relation as the **Single Source of Truth**.

### 🏗️ Body — The Machinery (`src/body/`, `src/services/`)

* Provides deterministic tools: auditing, filesystem operations, code parsing, git control.
* A centralized **Service Registry** ensures clean lifecycle management and singleton resources.

### ⚡ Will — The Reasoning Layer (`src/will/`)

* AI Agents that plan, write, and review code.
* Agents never act freely: **every action is pre‑validated** against the Constitution.

This creates a system that can **understand itself**, detect deviations, and evolve safely.

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
* **Roadmap** – Towards A2, A3, and full autonomous delivery
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
dpoetry run core-admin fix vector-sync --write

# 2. Run full audit
poetry run core-admin check audit

# 3. Try conversational commands
poetry run core-admin chat "make me a CLI tool that prints a random number"
```

---

## 🛠️ Common Commands

| Command                     | Description                                      |
| --------------------------- | ------------------------------------------------ |
| `make check`                | Run Lint, Test, Audit (full governance pipeline) |
| `core-admin fix all`        | Autonomous repair: headers, metadata, formatting |
| `core-admin inspect status` | Check DB, migrations, and registry health        |
| `core-admin run develop`    | Execute a complex, governed coding task          |

---

## 📄 License

Licensed under the **MIT License**. See `LICENSE`.
