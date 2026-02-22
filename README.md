# CORE

> **Executable constitutional governance for AI-assisted software development.**

---

## Executive Summary

CORE is a governance runtime that constrains AI agents with machine‑enforced constitutional law.

It enforces architectural invariants, blocks constitutionally invalid mutations automatically, and makes autonomous workflows auditable and deterministic.

LLMs operate inside CORE — never above it.

Most AI coding tools generate.
CORE constrains.

---

## 🎬 Live Enforcement Demo

Blocking rule → targeted drilldown → automated remediation → clean re‑validation.

[![asciicast](https://asciinema.org/a/BuS0WuKyRxQwYDHD.svg)](https://asciinema.org/a/BuS0WuKyRxQwYDHD)

This demo shows:

* A structural violation (`linkage.assign_ids`)
* Deterministic blocking of execution
* Rule‑level audit inspection
* Automated remediation via `core-admin dev sync --write`
* Verified compliance after repair

Governance is executable.

---

## What CORE Solves

### 1. Structural Drift in AI‑Generated Code

Without enforcement:

* Layer violations accumulate
* Architectural contracts degrade
* Implicit coupling spreads
* Files grow unbounded
* Technical debt becomes invisible

CORE enforces architectural invariants continuously.

Blocking rules halt execution.
Reporting rules surface structural debt.
Advisory rules expose risk signals.

---

### 2. Unsafe Autonomous Operations

Without constitutional enforcement:

```
Agent: "I'll delete the production database to fix this bug"
System: Executes command
You: 😱
```

With CORE:

```
Agent: "I'll delete the production database to fix this bug"
Constitution: BLOCKED — Violates data.ssot.database_primacy
System: Execution halted
You: 😌
```

CORE does not trust agents.
CORE verifies and enforces.

---

## Architectural Model

CORE separates responsibility into three constitutional layers.
This separation is law — not preference.

### 🧠 Mind — Law (`.intent/` + `src/mind/`)

Defines what is allowed, required, or forbidden.

* Machine‑readable constitutional rules
* Phase‑aware enforcement model
* Authority hierarchy (Meta → Constitution → Policy → Code)

Mind never executes.
Mind never mutates.
Mind defines law.

---

### ⚖️ Will — Judgment (`src/will/`)

Universal workflow model:

```
INTERPRET → ANALYZE → STRATEGIZE → GENERATE → EVALUATE → DECIDE
```

Will:

* Reads constitutional constraints
* Orchestrates reasoning
* Delegates execution
* Records traceable decisions

Will never bypasses Body.
Will never rewrites Mind.

---

### 🏗 Body — Execution (`src/body/`)

Deterministic components:

* Analyzers
* Evaluators
* Atomic Actions
* Resource Commands

Body performs mutations.
Body does not judge.
Body does not govern.

---

## System Guarantees

Within CORE:

* No file outside an autonomy lane can be modified
* No structural rule can be bypassed silently
* No database action occurs without authorization
* All decisions are phase‑aware and logged
* No agent can amend constitutional law

If a blocking rule fails, execution halts.

---

## Constitutional Primitives

| Primitive | Purpose                    |
| --------- | -------------------------- |
| Document  | Persisted artifact         |
| Rule      | Atomic normative statement |
| Phase     | When rule is evaluated     |
| Authority | Who decides                |

Enforcement strengths:

* Blocking
* Reporting
* Advisory

---

## Enforcement Engines

| Engine         | Method                              |
| -------------- | ----------------------------------- |
| ast_gate       | Deterministic structural validation |
| glob_gate      | Path and boundary enforcement       |
| intent_gate    | Runtime authorization               |
| knowledge_gate | Responsibility validation           |
| llm_gate       | LLM‑assisted semantic checks        |

Deterministic when possible.
LLM only when necessary.

---

## Current Capabilities

**Constitutional Enforcement**
60+ active rules across blocking, reporting, and advisory strengths.

**Governed Code Generation (A2)**
Natural language → constitutionally aligned code.

**Self‑Healing Compliance (A1)**
Automated structural and formatting correction.

**Universal Workflow (A2+)**
All autonomous operations share the same enforceable phase model.

---

## The Autonomy Ladder

```
A0 — Self‑Awareness        ✅
A1 — Self‑Healing          ✅
A2 — Governed Generation   ✅
A2+ — Universal Workflow   ✅  (current)
A3 — Strategic Refactoring 🎯
A4 — Self‑Replication      🔮
```

---

## Quick Start

```bash
git clone https://github.com/DariuszNewecki/CORE.git
cd CORE
poetry install

cp .env.example .env
make db-setup

poetry run core-admin check audit
```

---

## Documentation

[https://dariusznewecki.github.io/CORE/](https://dariusznewecki.github.io/CORE/)

---

## Project Status

Current Release: v2.2.0 — Universal Workflow Pattern

Test coverage: 14% (target: 75%)
Pattern migration: in progress
Legacy code: being retired incrementally

---

## License

MIT License

---

<div align="center">

**Build fast with AI. Stay constitutionally aligned.**

</div>
