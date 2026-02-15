# CORE

> **A constitutional orchestrator for AI‑assisted development.**

[![Status: A2+ Universal Workflow](https://img.shields.io/badge/status-A2%2B%20Universal%20Workflow-brightgreen.svg)](#-project-status)
[![Governance: Constitutional](https://img.shields.io/badge/governance-Constitutional-blue.svg)](#-constitutional-governance)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://dariusznewecki.github.io/CORE/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![codecov](https://codecov.io/gh/DariuszNewecki/CORE/graph/badge.svg)](https://codecov.io/gh/DariuszNewecki/CORE)

**CORE is not a coding agent.** CORE is the governance runtime and workflow orchestrator that constrains coding agents — LLMs, tools, scripts — with machine‑enforced constitutional rules.

It ensures that AI‑assisted development remains structurally sound, traceable, and aligned from day one.

CORE is governed by an **immutable, machine-readable Constitution** stored in `.intent/`.
Contributions, autonomous behavior, and system evolution are **subordinate to the Constitution**.
Changes that violate intent are rejected — even if tests pass.

This is operational, actively evolving code. Not a research paper. Not a prototype.

---

## 🎬 See Constitutional Governance in Action

[![asciicast](https://asciinema.org/a/S4tXkXUclYeTo6kEH1Z5UyUPE.svg)](https://asciinema.org/a/S4tXkXUclYeTo6kEH1Z5UyUPE)

[View full screen →](https://asciinema.org/a/S4tXkXUclYeTo6kEH1Z5UyUPE)

**What you're seeing:**

* AI agent generates code autonomously
* Constitutional auditor validates every change
* Violations caught and blocked
* Governance enforced without human intervention

---

## 🚨 What CORE Solves

### Problem 1: Structural Drift in AI‑Generated Code

AI tools generate code quickly — but without enforcement, codebases decay: layer violations, duplication, contract drift, oversized files, hidden coupling.

CORE continuously enforces architectural invariants.

### Problem 2: Unsafe Autonomous Operations

Without structural enforcement:

```
Agent: "I'll delete the production database to fix this bug"
System: ✅ Executes command
You: 😱
```

With CORE:

```
Agent: "I'll delete the production database to fix this bug"
Constitution: ❌ BLOCKED — Violates data.ssot.database_primacy
System: Halts. Surfaces violation.
You: 😌
```

CORE does not "trust" agents. CORE verifies and enforces.

---

## 🏛️ How It Works

CORE separates responsibility into three architectural layers. This separation is constitutional law, not organizational convenience.

### 🧠 Mind — Law & Governance (`.intent/` + `src/mind/`)

Human-authored, machine-readable rules:

```yaml
rules:
  - id: autonomy.lanes.boundary_enforcement
    statement: Autonomous agents MUST NOT modify files outside their assigned lane
    enforcement: blocking
    authority: constitution
    phase: runtime
```

The Constitution is the **highest authority**. Code, agents, and workflows are subordinate.

Mind defines what is allowed, required, or forbidden. **Mind is law, not execution.** Mind never performs I/O, never makes strategic decisions, never invokes actions.

---

### 🏗️ Body — Pure Execution (`src/body/`)

Deterministic building blocks:

* **Analyzers** — extract facts, make no decisions
* **Evaluators** — detect quality issues and violations
* **Atomic Actions** — governed mutations with explicit parameters

Body receives instructions and executes them. **Body is capability, not judgment.** Body never chooses between alternatives, never evaluates constitutional rules, never orchestrates.

---

### ⚡ Will — Decision & Orchestration (`src/will/`)

The workflow engine that composes operations using a universal phase model:

```
INTERPRET → ANALYZE → STRATEGIZE → GENERATE → EVALUATE → DECIDE
```

Will reads Mind to understand constraints. Will delegates execution to Body. **Will is judgment, not law or execution.** Will never implements actions directly, never bypasses Body, never modifies Mind.

Agents propose. CORE orchestrates. Evaluators validate. The Constitution enforces.

---

## 🔒 Constitutional Primitives

CORE is built on exactly four primitives:

| Primitive     | Purpose                                          |
| ------------- | ------------------------------------------------ |
| **Document**  | A persisted artifact that CORE may load           |
| **Rule**      | An atomic normative statement (true or false)     |
| **Phase**     | When a rule is evaluated (Parse → Load → Audit → Runtime → Execution) |
| **Authority** | Who decides (Meta → Constitution → Policy → Code) |

Rules declare enforcement strength: **Blocking**, **Reporting**, or **Advisory**. Enforcement is orthogonal to Phase and Authority. All governance collapses into a single evaluative model — no special cases.

---

## ⚙️ Enforcement Engines

Constitutional rules are enforced by deterministic engines:

| Engine             | Method                                      |
| ------------------ | ------------------------------------------- |
| **ast_gate**       | AST inspection — import boundaries, naming, purity checks |
| **glob_gate**      | Path-based enforcement — file location, structure |
| **intent_gate**    | Runtime action authorization — whitelist/blacklist |
| **knowledge_gate** | Semantic responsibility verification         |
| **llm_gate**       | LLM-assisted semantic analysis for complex checks |

Why AST over LLM for structural rules: deterministic, fast, precise, cacheable.

---

## 📊 Current Capabilities

**Constitutional Enforcement:**
60+ rules actively enforced across blocking, reporting, and advisory strengths. Phase-aware violation detection with deterministic engine dispatch.

**Governed Code Generation (A2):**
Feature generation from natural language, constrained by constitutional rules. Architectural consistency enforcement. Adaptive strategy pivots on failure.

**Self-Healing Compliance (A1):**
Automated formatting, docstring, and structure fixes. All mutations governed by constitutional workflow.

**Universal Workflow (A2+):**
All autonomous operations compose through the same phase model. Operations are self-correcting, traceable, and composable.

---

## 🎯 The Autonomy Ladder

CORE governs autonomous workflows within defined constitutional scope. Each level adds capability while maintaining enforcement:

```
A0 — Self-Awareness        ✅  CORE understands its own structure
A1 — Self-Healing          ✅  Automated compliance fixes
A2 — Governed Generation   ✅  Constitutional code generation
A2+ — Universal Workflow   ✅  YOU ARE HERE
A3 — Strategic Refactoring 🎯  Proposal-based autonomous action
A4 — Self-Replication      🔮  Future
```

---

## 🔥 What Makes CORE Different

| Aspect          | Traditional AI Tools      | CORE                              |
| --------------- | ------------------------- | --------------------------------- |
| Safety          | Prompt discipline         | Structural constitution           |
| Enforcement     | Best effort               | Blocking rules, engine-dispatched |
| Correction      | Per-command retry          | Phase-aware workflow governance   |
| Governance      | Implicit / tribal         | Machine-readable, four primitives |
| Auditability    | Logs                      | Phase-aware decision trails       |
| Agent trust     | Assumed                   | Never — verify and enforce        |

**Key principle:** Safety and self-correction are **architectural properties**, not prompt instructions.

---

## What CORE Is Not

* **Not a coding agent** — CORE constrains agents, it does not replace them
* **Not a general AGI** — CORE is a governance runtime with defined scope
* **Not a replacement for engineers** — CORE augments engineers and constrains agents
* **Not a framework** — CORE implements a constitutional governance model that defines what is allowed
* **Not a black-box autonomous system** — every decision is traceable to constitutional law

CORE possesses no authority to amend its own constitution, suppress rules, or introduce exceptions. If the constitution is defective, CORE halts — it does not invent behavior to preserve continuity.

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

* Constitutional architecture
* Governance model and primitives
* Mind/Body/Will separation
* Universal workflow pattern
* Enforcement engines
* Autonomy ladder

---

## 📊 Project Status

**Current Release:** v2.2.0 — Universal Workflow Pattern

**Transparency:**

* Test coverage: 14% (target: 75%)
* Pattern migration: in progress
* Legacy code: being retired incrementally

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) — constitutional literacy required.

---

## 📄 License

MIT License.

---

<div align="center">

**CORE: Build fast with AI. Stay structurally aligned.**

</div>
