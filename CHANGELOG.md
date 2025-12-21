# Changelog

All notable changes to this project are documented in this file.

This project follows **Keep a Changelog** and **Semantic Versioning**, but with an explicit focus on **governance maturity and autonomy progression**, not just features.

---

## [2.1.0] — 2025-01 (Unreleased)

### 🎯 Consolidation Release — Governance First

This release focuses on **stabilisation, credibility, and enforcement depth**, rather than expanding raw capability. It represents the transition from *capability discovery* to *governance consolidation*.

### Added

#### Governance & Enforcement

* Enforcement coverage tracking promoted to **first-class governance signal**
* Explicit distinction between **declared vs enforced** constitutional rules
* Coverage regeneration and drift detection for governance audits
* Progressive disclosure output for enforcement results (CLI-first)

#### Autonomy Discipline

* Formalisation of **A2 Governed Autonomy** (coverage-bounded)
* Explicit autonomy ladder definitions embedded in documentation
* Clear separation between *capability existence* and *operational autonomy*

#### Documentation & Communication

* README rewritten for **credibility calibration** and human-friendly tone
* Clear articulation of *what CORE does not yet do*
* Alignment between metrics, autonomy claims, and enforcement scope

### Changed

* Reframed A2 status from "achieved" to **"governed and bounded"**
* Reduced implicit hype in public-facing descriptions
* Tightened language around autonomy, authority, and responsibility

### Removed

* Implicit assumptions that autonomy == coverage completeness

---

## [2.0.0] — 2024-11-28

### 🎯 Major Milestone: A2 Governed Code Generation (Foundational)

This release marked the **first operational realization of A2 autonomy**: the ability to autonomously generate new code under **constitutional governance**, with semantic awareness and enforced constraints.

This version established the **technical spine** of CORE.

### Added

#### Governed Code Generation (A2 — Foundational)

* **CoderAgent v1**: Context-aware autonomous code generation (70–80% success)
* **Semantic Infrastructure**: 500+ symbols vectorized, 60+ module anchors
* **Context Package System**: Structured, reproducible AI context construction
* **Semantic Placement**: Deterministic code placement accuracy
* **Policy Vectorization**: Agents reason semantically over constitutional rules
* **Architectural Context Builder**: System-wide structural awareness for agents
* **Module Anchors**: Semantic markers for placement and governance

#### Constitutional Governance

* **Constitutional Audit System**: Continuous validation with violation tracking
* **Micro-Proposal Loop**: Autonomous remediation proposals (governed)
* **Policy Coverage Service**: Mapping between rules and code regions
* **Agent Governance Policies**: Explicit autonomy lanes and prohibitions

#### Infrastructure & Runtime

* **Service Registry**: Deterministic lifecycle and dependency management
* **PostgreSQL Knowledge Graph**: Symbols and relations as SSOT
* **Vector Store Integration**: Semantic search over code and policies
* **Test Isolation**: Dedicated test database and execution paths

### Changed

#### Context & Reasoning

* Migration from ad-hoc string prompts to **structured ContextPackages**
* Architectural and policy context injected deterministically
* Improved reasoning traceability and reproducibility

#### Agent Behaviour

* Agents constrained to **explicitly permitted actions only**
* All AI output subject to constitutional validation
* Failure paths produce structured diagnostics

#### Quality & Validation

* Test generation improved through semantic awareness
* Governance checks integrated into standard workflows

### Fixed

* Dependency injection lifecycle inconsistencies
* Semantic placement drift
* Database session handling
* Import, header, and docstring compliance gaps

### Performance Signals (Indicative)

* Code generation success: ~70–80%
* Semantic placement accuracy: ~100%
* Knowledge graph growth: 0 → 500+ symbols

---

## [1.0.0] — 2024-10-01

### 🎯 Major Milestone: A1 Self-Healing Autonomy

Initial public release establishing **governed self-healing** as a first-class capability.

### Added

#### Self-Healing (A1)

* Autonomous docstring generation
* Header and metadata compliance
* Import organisation and formatting
* Policy-driven repair actions

#### Foundations

* Mind–Body–Will architecture
* Constitutional governance via `.intent/`
* Policy-driven validation model
* Initial agent framework

#### Tooling

* `core-admin` CLI
* Constitutional audit commands
* Autonomous repair workflows

---

## Autonomy Levels (Reference)

* **A0 — Self-Awareness**: Knowledge graph, symbol discovery
* **A1 — Self-Healing**: Autonomous compliance and drift repair
* **A2 — Governed Generation**: Code generation under enforced rules
* **A3 — Strategic Refactoring**: Multi-file architectural change (planned)
* **A4 — Self-Replication**: CORE generates CORE.NG from intent (conceptual)

---

### Notes

* Autonomy levels describe **operational behavior**, not theoretical capability.
* Advancement requires **measurable enforcement coverage**, not feature presence.

---

[2.1.0]: https://github.com/DariuszNewecki/CORE/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/DariuszNewecki/CORE/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/DariuszNewecki/CORE/releases/tag/v1.0.0
