# CORE

> **The first AI coding agent with a universal operating system for autonomous operations.**

[![Status: A2+ Universal Workflow](https://img.shields.io/badge/status-A2%2B%20Universal%20Workflow-brightgreen.svg)](#-project-status)
[![Governance: Constitutional](https://img.shields.io/badge/governance-Constitutional-blue.svg)](#-constitutional-governance)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://dariusznewecki.github.io/CORE/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![codecov](https://codecov.io/gh/DariuszNewecki/CORE/graph/badge.svg)](https://codecov.io/gh/DariuszNewecki/CORE)

**CORE solves two problems:**

1. **AI safety:** Immutable constitutional rules that AI cannot bypass
2. **Autonomous operations:** Universal workflow pattern that closes all loops

Most AI agents operate on vibes and prompt engineering. CORE enforces **constitutional governance** through a **universal orchestration model** that makes every operation self-correcting, traceable, and composable.

CORE is governed by an **immutable, machine-readable Constitution** stored in `.intent/`.
Contributions, autonomous behavior, and system evolution are **subordinate to the Constitution**.
Changes that violate intent are rejected — even if tests pass.

This is working, production-ready code. Not a research paper. Not a prototype.

---

## 🎬 See Constitutional Governance in Action

[![asciicast](https://asciinema.org/a/S4tXkXUclYeTo6kEH1Z5UyUPE.svg)](https://asciinema.org/a/S4tXkXUclYeTo6kEH1Z5UyUPE)

[View full screen →](https://asciinema.org/a/S4tXkXUclYeTo6kEH1Z5UyUPE)

**What you're seeing:**

* AI agent generates code autonomously
* Constitutional auditor validates every change
* Violations caught and auto-remediated
* Zero human intervention required

---

## 🚨 The Problem CORE Solves

### Problem 1: AI Without Guardrails

**Current AI coding agents:**

```
Agent: "I'll delete the production database to fix this bug"
System: ✅ Executes command
You: 😱
```

**CORE:**

```
Agent: "I'll delete the production database to fix this bug"
Constitution: ❌ BLOCKED — Violates data.ssot.database_primacy
System: ✅ Auto-remediated to safe operation
You: 😌
```

### Problem 2: Ad-Hoc Workflows

**Current approach:**

```python
def fix_clarity(file):
    for attempt in range(3):
        result = llm.refactor(file)
        if looks_good(result):
            break
    save(result)
```

**CORE's Universal Workflow:**

```python
INTERPRET → ANALYZE → STRATEGIZE → GENERATE → EVALUATE → DECIDE

if not evaluator.solved():
    if strategist.should_pivot():
        strategy = strategist.adapt(failure_pattern)
    continue_loop()
```

---

## 🎯 What's New in 2.2.0: The Operating System

**CORE now has a universal orchestration model** that composes all autonomous operations.

### The Universal Workflow Pattern

Every autonomous operation—from simple file fixes to full feature development—follows this pattern:

```
INTERPRET → ANALYZE → STRATEGIZE → GENERATE → EVALUATE → DECIDE
```

**What this enables:**

* Self-correction as a system property
* Phase-aware governance enforcement
* Composable autonomous workflows

**Result:** CORE becomes an **operating system for AI-driven development**, not just a toolset.

---

## 🏛️ How It Works: Constitutional AI Governance + Universal Orchestration

### 🧠 Mind — The Constitution (`.intent/`)

Human-authored rules stored as immutable YAML:

```yaml
rules:
  - id: autonomy.lanes.boundary_enforcement
    statement: Autonomous agents MUST NOT modify files outside their assigned lane
    enforcement: blocking
    authority: constitution
    phase: runtime
```

The Constitution is the **highest authority in CORE**.
Code, tests, and agents are implementation details.

---

### 🏗️ Body — The Execution Layer (`src/body/`)

Components are organized by **workflow phase**:

* Analyzers (facts, no decisions)
* Evaluators (quality and failure detection)
* Atomic Actions (governed mutations)

These are reusable building blocks, not one-off logic.

---

### ⚡ Will — The Orchestration Layer (`src/will/`)

Strategists make deterministic decisions.
Orchestrators compose adaptive workflows.

Every loop is **self-correcting by design**.

---

## 📊 Current Capabilities

### ✅ Autonomous Code Generation (A2)

* Feature generation from natural language
* Architectural consistency enforcement
* Adaptive strategy pivots

### ✅ Self-Healing Compliance (A1)

* Automated formatting, docstring, and structure fixes
* Universal workflow enforcement

### ✅ Constitutional Auditing

* 60+ rules actively enforced
* Phase-aware violation detection

---

## 🏗️ Component Architecture (2.2.0)

40+ components mapped to constitutional phases.

**Enables:**

* Reusability
* Composability
* Traceability
* Testability

---

## 🎯 The Autonomy Ladder

```
A0 — Self-Awareness        ✅
A1 — Self-Healing          ✅
A2 — Governed Generation   ✅
A2+ — Universal Workflow   ✅ YOU ARE HERE
A3 — Strategic Refactoring 🎯
A4 — Self-Replication      🔮
```

A2+ establishes the **architectural foundation** for A3 and beyond.

---

## 🔥 Why This Is Different

| Feature         | Traditional Agents | CORE                    |
| --------------- | ------------------ | ----------------------- |
| Safety          | Prompt discipline  | Structural constitution |
| Enforcement     | Best effort        | System-level blocking   |
| Self-correction | Per-command        | Universal               |
| Governance      | Tribal             | Machine-readable        |
| Auditability    | Logs               | Phase-aware trails      |

**Key insight:** Self-correction and safety must be **architectural properties**, not features.

---

## 🚀 Quick Start

```bash
git clone https://github.com/DariuszNewecki/CORE.git
cd CORE
poetry install

cp .env.example .env
make db-setup

poetry run core-admin check audit
```

---

## 📚 Documentation

🌐 [https://dariusznewecki.github.io/CORE/](https://dariusznewecki.github.io/CORE/)

* Architecture
* Governance model
* Universal workflow
* Components
* Autonomy ladder

---

## 🏆 What Makes This Novel

1. One of the first production-grade implementations of constitutional AI governance
2. Universal workflow pattern that closes all autonomous loops
3. Semantic policy understanding
4. Structurally immutable constitution with procedural enforcement gates
5. Progressive, safety-gated autonomy

---

## 📊 Project Status

**Current Release:** v2.2.0 — Universal Workflow Pattern

**Transparency:**

* Test coverage: 14% (target: 75%)
* Pattern migration: in progress
* Legacy code: being retired incrementally

---

## 🤝 Contributing

**Contributing:** See [CONTRIBUTING.md](CONTRIBUTING.md) — constitutional literacy required.

---

## 📄 License

MIT License.

---

<div align="center">

**CORE: Where intelligence meets accountability meets orchestration.**

</div>
