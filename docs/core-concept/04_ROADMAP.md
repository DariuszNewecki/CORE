# CORE Roadmap

This roadmap reflects the **current reality** of CORE’s codebase (as of 2025) and the **planned next stages** of its evolution.
It is intentionally conservative: everything marked *Shipped* exists in `src/`, everything marked *Planned* is architectural direction, and nothing here promises unimplemented features.

The goal is simple:

> **Evolve CORE from a governed development framework (A1) into a safely autonomous system (A2 → A3) without ever compromising constitutional control.**

---

## 1. Status Overview

### ✅ **A1 — Governed Generation (Current State)**

CORE today already supports:

* Crate creation for new features and fixes
* Context building (Body → Will)
* AI-driven code & test generation (Will)
* Local validation (formatting, linting, tests)
* Full constitutional audits (Mind)
* Accept/reject cycle for crates
* Knowledge Graph & symbol discovery
* Extensive introspection & self-healing tools

This forms the stable foundation of A1.

---

## 2. Near-Term Roadmap (A1 → A2)

These are realistic, incremental enhancements fully consistent with current architecture.

### 🧩 **2.1. Autonomous Cycle Improvements (A1.5)**

**Goal:** Improve reliability, accuracy, and clarity of autonomous generation.

Planned:

* Better crate metadata (more explicit boundaries)
* Richer context selection (more relevant source extraction)
* Improved test generation heuristics
* Enhanced self-healing pipelines (IDs, docs, structure)
* More detailed audit output for crate rejection

All items extend existing systems without introducing new complexity.

---

### 🧠 **2.2. Intent-Aware Agents (A2)**

**Goal:** Agents reason using Mind knowledge instead of generic prompts.

Planned:

* Agents consume `.intent/` rules directly
* Agents select capabilities from Knowledge Graph
* Validation Pipeline upgraded to catch semantic misalignment
* Planner Agent becomes constraint-driven rather than free-form

Outcome:
Agents obey constitutional rules not just after generation, but **during** generation.

---

## 3. Medium-Term Roadmap (A2 → A3)

These require more coordination across Mind–Body–Will.

### ⚙️ **3.1. Autonomous Refactoring (Governed)**

**Goal:** Enable safe, governed structural improvements.

Planned:

* Drift-aware refactor suggestions
* Localized structural cleanups
* Autonomous but governed: changes still occur through crates

No direct file writes, no bypass of audits.

---

### 📦 **3.2. Capability-Aware Planning**

**Goal:** Replace ad-hoc prompt reasoning with capability-based planning.

Planned:

* Planner Agent selects capabilities from Knowledge Graph
* Will reasons in terms of *actions CORE can perform*
* Plans become reproducible and auditable

This is foundational for long-term stability.

---

### 🔍 **3.3. Deeper Knowledge Graph Integration**

Planned:

* More relationships in the graph (imports, dependencies, test coverage)
* Semantic clustering of capabilities
* Knowledge-driven test generation

Outcome:
CORE begins to *understand itself* at a structural level.

---

## 4. Long-Term Vision (A3 → A4)

These goals are ambitious but aligned with the design.

### 🏛 **4.1. Fully Governed Autonomous Maintenance**

CORE maintains itself:

* Enforces coverage thresholds
* Detects drift & decay
* Unifies test strategy & quality rules
* Generates routine maintenance PRs autonomously

Changes still go through crate → validation → audit.

---

### 👁 **4.2. Constitutional Self-Evolution**

Already partially implemented through:

* Proposal workflow
* Human signature requirements
* Canary evaluation

Long-term goal:

* Agents propose constitutional changes
* Humans approve or reject
* Constitution evolves safely

---

### 🎛 **4.3. Multi-Agent Collaboration**

Multiple agents coordinate under the Mind:

* Planner → Analyzer → Coder → Reviewer
* Shared context
* Shared capability set

Still fully governed.

---

## 5. Anti-Goals (Things CORE Will Not Become)

To avoid architectural drift or feature sprawl, CORE **will not**:

* Become a generic unrestricted auto-coder
* Execute code outside governed workflows
* Allow agents to bypass the Mind
* Replace CI pipelines
* Accept uncontrolled code generation or refactoring

CORE’s strength is governance, not speed at all costs.

---

## 6. Roadmap Summary

| Stage | Name                         | Focus                                       | Status      |
| ----- | ---------------------------- | ------------------------------------------- | ----------- |
| A1    | Governed Generation          | Autonomous crates, audits, validation       | **Shipped** |
| A1.5  | Autonomous Improvement       | Context, metadata, stability                | **Planned** |
| A2    | Intent-Aware Planning        | Agents reason using Mind constraints        | **Planned** |
| A2.5  | Knowledge-Driven Development | Capability-based reasoning                  | **Planned** |
| A3    | Governed Refactoring         | Safe, autonomous structural changes         | **Planned** |
| A4    | Self-Evolving Constitution   | Agents propose Mind changes, humans approve | **Vision**  |

---

## 7. Guidance for Contributors

If you’re implementing features described here:

* Stay aligned with Mind–Body–Will
* Never bypass audits or `.intent/`
* Treat roadmap items as **direction**, not requirements
* Keep interfaces stable and explicit
* Prefer small, well-bounded capabilities

---

CORE evolves deliberately, not quickly.
Governance always comes first.

Next:
🔸 [Autonomy Ladder](05-autonomy-ladder.md)
🔸 [Context & Comparisons](06-context-and-comparisons.md)
