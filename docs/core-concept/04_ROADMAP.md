# CORE Roadmap

> **Status:** Active
> **Last Updated:** 2025-11-24
> **Current Phase:** Entering A2 (Intent-Aware Agents)

This roadmap reflects the **current reality** of CORE’s architecture (post–Service Registry, DB-as-SSOT, strict DI) and the **planned next stages** of its evolution.
It is intentionally conservative: everything marked **Shipped** exists in `src/`, and nothing here promises speculative or ungrounded features.

The goal is simple:

> **Evolve CORE from a governed development framework (A1) into a safely autonomous system (A2 → A3 → A4) without ever compromising constitutional control.**

---

# 1. Status Overview

## ✅ A1 — Governed Generation *(Shipped)*

CORE today already supports:

* **Crate-based development** (no direct writes)
* **Context building** (Body → Will)
* **AI-driven code + test generation**
* **Formatter/linter/test validation**
* **Full Constitutional Audit** (Mind)
* **Accept/reject crate cycle**
* **Introspection & Knowledge Graph sync**
* **Vectorized semantic memory**

This constitutes a complete A1 governed development loop.

---

## ✅ A1.5 — Structural Stability *(Shipped)*

Foundational hardening of CORE’s infrastructure:

* **Service Registry** eliminates split-brain service instantiation
* **Database-as-SSOT**: all symbols, capabilities, and metadata unified in Postgres
* **Self-Healing**: Autonomous fixing of IDs, headers, docstrings, structure
* **Qdrant + Knowledge Graph synchronization** now stable

These upgrades complete the transition to an A2-ready architecture.

---

# 2. Near-Term Roadmap (A2: The "Will" Awakening)

With architecture stabilized, the focus moves to enhancing the **Will** (Agents).

## 🧠 2.1 Intent-Aware Agents *(Active)*

**Goal:** Agents reason using constitutional rules, not generic prompts.

Planned / Under Construction:

* [ ] **Context-Aware Planning:** Planner Agent queries Knowledge Graph to understand existing capabilities
* [ ] **Constitution-in-Loop:** Agents receive `.intent/` constraints dynamically
* [ ] **Semantic Validation Pipeline:** Detect misaligned but syntactically valid code
* [ ] **Policy-Constrained Generation:** Will must respect boundaries *during* generation, not after

Outcome:
Agents behave as governed actors, not free text predictors.

---

## 📦 2.2 Capability-First Development *(Transition Phase)*

**Goal:** Development becomes capability-based instead of file-based.

Planned:

* [ ] **Capability Selection UI/Query:** Agents browse `core.capabilities` before generating code
* [ ] **Reuse Analyzer:** "Does this already exist?" checks before writing new functions
* [ ] **Refactoring Agent:** Dedicated agent for eliminating duplication & debt

This enables consistent, reusable reasoning.

---

# 3. Medium-Term Roadmap (A2 → A3)

These stages deepen integration of Mind, Body, and Will.

## ⚙️ 3.1 Autonomous Refactoring *(Planned)*

**Goal:** Safe, governed structural improvements.

Capabilities:

* Drift-aware refactor proposals
* Dead-code detection & cleanup
* Intelligent, localized structure improvements
* Still fully governed: Crate → Audit → Canary → Commit

No bypasses, no direct writes.

---

## 🔍 3.2 Deep Knowledge Graph Integration *(Planned)*

Enhancements:

* Semantic clustering of capabilities
* Import/dependency graphing
* Knowledge-driven test generation
* Change-impact analysis ("If we modify X, what breaks?")

Outcome: CORE begins to *understand itself* structurally.

---

# 4. Long-Term Vision (A3 → A4)

## 🏛 4.1 Constitutional Self-Evolution *(Vision)*

Already partially implemented via proposals + human signatures.

Future goals:

* Agents propose amendments to `.intent/policies`
* Humans review/cryptographically sign
* Constitution evolves safely over time

---

## 🎛 4.2 Multi-Agent Collaboration *(Vision)*

Roles:

* **Planner** designs architectural intent
* **Analyzer** searches capability graph for matches
* **Coder** implements governed modifications
* **Auditor (AI)** checks constitutional alignment
* **Reviewer (Human)** validates outcomes

Still fully governed.

---

# 5. Anti-Goals (Non-Objectives)

To avoid architectural drift and unsafe autonomy, CORE will **not**:

* Become a generic auto-coder
* Execute code outside governed workflows
* Allow agents to bypass `.intent/` or DB SSOT
* Replace CI pipelines
* Permit uncontrolled refactoring or generation

Governance > Speed.

---

# 6. Roadmap Summary

| Stage | Name                         | Focus                                        | Status      |
| ----: | ---------------------------- | -------------------------------------------- | ----------- |
|    A1 | Governed Generation          | Autonomous crates, audits, validation        | **Shipped** |
|  A1.5 | Structural Stability         | Service Registry, SSOT, Self-Healing         | **Shipped** |
|    A2 | Intent-Aware Agents          | Context-driven planning, reuse, constitution | **Active**  |
|  A2.5 | Capability-Based Development | Knowledge Graph reasoning                    | **Planned** |
|    A3 | Autonomous Refactoring       | Proactive, governed code improvements        | **Planned** |
|    A4 | Self-Evolving Constitution   | Agents propose Mind changes                  | **Vision**  |

---

# 7. Guidance for Contributors

When contributing to roadmap items:

* **Align with Mind–Body–Will** at all times
* **Never bypass audits or `.intent/`**
* **Use only DI-provided services (ServiceRegistry)**
* **Favor small, explicit, capability-based changes**
* **Document new capabilities** for the Knowledge Graph

---

CORE evolves deliberately — not quickly — because **governance comes first**.

Next:

* 🔸 **Autonomy Ladder (`05-autonomy-ladder.md`)**
* 🔸 **Context & Comparisons (`06-context-and-comparisons.md`)**
