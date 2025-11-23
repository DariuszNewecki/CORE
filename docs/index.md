# CORE Documentation

Welcome to the **CORE Documentation Hub** — the complete guide to understanding, operating, and extending the **Constitutional, Self‑Governing AI Development Framework**.

CORE is built on a clear architectural model:

* **Mind** — Governance, policies, constitutional rules (`src/mind/`)
* **Body** — Execution engine, CLI, services, actions (`src/body/`, `src/features/`, `src/services/`)
* **Will** — Agents, reasoning, LLM orchestration (`src/will/`)

The purpose of this documentation is to give you a clean, accurate, and up‑to‑date entry point into the system — free from architectural drift, speculative features, or outdated assumptions.

---

## 🚀 Getting Started

If you are new to CORE, start with these pages:

### **1. What is CORE?**

A clear explanation of the philosophy and motivation behind the project.

* [What is CORE?](core-concept/00_WHAT_IS_CORE.md)

### **2. Architecture Overview**

How CORE is structured internally: Mind–Body–Will, governance model, lifecycle.

* [Architecture](core-concept/02_ARCHITECTURE.md)

### **3. How Governance Works**

Learn how the `.intent/` constitution controls everything CORE does.

* [Governance Model](core-concept/03_GOVERNANCE.md)

### **4. QuickStart Guides**

If you want to run CORE immediately:

* [Starter Kits](getting-started/01-starter-kits.md)
* [Bring Your Own Runtime](getting-started/02-byor.md)

---

## ⚙️ How to Use CORE

CORE exposes a powerful CLI called **`core-admin`**, which integrates:

* Constitutional audits
* Autonomous development
* Context building
* Knowledge syncing
* Self‑healing and remediation

To explore the CLI:

```bash
poetry run core-admin --help
poetry run core-admin inspect command-tree
```

You will find detailed explanations in:

* [CLI Reference](developer-guide/03-cli-reference.md)
* [CLI Command Index](developer-guide/04-cli-commands-table.md)
* [CLI Workflows](developer-guide/05-cli-workflows.md)

---

## 🧠 Autonomous Development (Shipped Today)

CORE can already:

* Create governed **feature crates**
* Use AI agents to generate code, tests, and documentation
* Validate all changes locally (Black, Ruff, Pytest)
* Run full constitutional audits via the Mind
* Accept or reject crates based on compliance

Learn exactly what works today:

* [Autonomous Development Overview](autonomous-development/00-overview.md)

---

## 📚 Deep Concepts & Internal Knowledge

If you want to understand CORE beyond its interface, explore:

* [Philosophy](core-concept/01_PHILOSOPHY.md)
* [Autonomy Ladder](core-concept/05-autonomy-ladder.md)
* [Context & Comparisons](core-concept/06-context-and-comparisons.md)
* [Worked Example](core-concept/07-worked-example.md)

For internal mechanics:

* [Introspection & Knowledge](context-and-knowledge/01-integration-todo.md)
* [ContextPackage](context-and-knowledge/context-package/readme.md)

---

## 🛠 Developer Resources

For contributors or maintainers of CORE:

* [Contributing Guidelines](developer-guide/01-contributing.md)
* [Developer Cheat Sheet](developer-guide/02-cheatsheet.md)
* [Technical Debt & Structure Notes](developer-guide/06-technical-debt.md)

Planning documents:

* [Complete Implementation Plan](planning/01-complete-implementation-plan.md)
* [Restructure Plan](planning/03-restructure-plan.md)
* [Release Notes](planning/releases/v0.2.0.md)

---

## 🧵 Autonomy & Governance

To understand how CORE keeps itself safe, governed, and free from structural drift:

* [Peer Review](autonomy-and-governance/01-peer-review.md)
* [Complexity Filtering](autonomy-and-governance/02-complexity-filtering.md)
* [Pragmatic Test Generation](autonomy-and-governance/03-test-generation-pragmatics.md)

Constitutional coverage & enforcement:

* [Coverage Quick Reference](autonomy-and-governance/constitutional-coverage/quick-reference.md)
* [Implementation Checklist](autonomy-and-governance/constitutional-coverage/implementation-checklist.md)

---

## 📖 Reference Materials

API and capability listings:

* [API Reference](reference/01-api-reference.md)
* [Capability Reference](reference/02-capability-reference.md)

---

## 🗄 Archive

Historical and older planning materials:

* [Academic Paper Draft](archive/11_ACADEMIC_PAPER.md)
* [Strategic Plan (Legacy)](archive/StrategicPlan.md)

---

## 🎯 About This Documentation

This documentation is structured to:

* Stay aligned with the **actual codebase** (no speculative features)
* Reflect the **current state of autonomy** (A1 → A2)
* Support ongoing development of governed AI systems
* Serve as a clean entry point for new contributors

If you ever find a discrepancy between docs and code, treat it as a bug.

Welcome to CORE — a system designed not just to run code, but to **govern its own evolution**.
