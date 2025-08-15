# CORE — The Self-Improving System Architect

> **Where Intelligence Lives.**

[![Status: Architectural Prototype](https://img.shields.io/badge/status-architectural%20prototype-blue.svg)](#-project-status)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

CORE is a self-governing, constitutionally aligned AI development framework that can plan, write, validate, and evolve software systems — autonomously and safely. It is designed for environments where **trust, traceability, and governance matter**.

---

## 🏛️ Project Status: Architectural Prototype

The core self-governance and constitutional amendment loop is complete and stable. The system can audit and modify its own constitution via a human-in-the-loop, cryptographically signed approval process.

The next phase, as outlined in our **[Project Roadmap](docs/04_ROADMAP.md)**, is to expand agent capabilities so CORE can generate and manage entirely new applications based on user intent.

We’re making the project public now to invite collaboration on this foundational architecture.

---

## 🧠 What CORE *is*

* 🧾 Evolves itself through **declared intent**, not hidden assumptions.
* 🛡️ Enforces **constitutional rules**, **domain boundaries**, and **safety policies**.
* 🌱 Creates new, governed applications from **[Starter Kits](docs/06_STARTER_KITS.md)** that capture initial intent.
* 🧩 Uses a modular agent architecture with a clear separation of concerns.
* 📚 Ensures every decision is **documented, reversible, and introspectable**.

---

## 🦮 Key Concepts

| Concept                     | Description                                                                              |
| --------------------------- | ---------------------------------------------------------------------------------------- |
| **`.intent/`**              | The “mind” of CORE: constitution, policies, capability maps, and self-knowledge.         |
| **`ConstitutionalAuditor`** | The “immune system,” continuously verifying code aligns with the constitution.           |
| **`PlannerAgent`**          | Decomposes high-level goals into executable plans.                                       |
| **`core-admin` CLI**        | Human-in-the-loop tool for managing the system's lifecycle.                              |
| **Starter Kits**            | Pre-packaged constitutions that serve as the user's first declaration of intent.         |
| **Canary Check**            | Applies proposed changes to an isolated copy and runs a full self-audit before approval. |
| **Knowledge Graph**         | Machine-readable map of symbols, roles, capabilities, and relationships.                 |

---

## 🚀 Getting Started

1. **Install dependencies**

   ```bash
   poetry install
   ```

2. **Set up environment**

   ```bash
   cp .env.example .env
   # Edit .env with your keys/URLs.
   # See .intent/config/runtime_requirements.yaml for required variables.
   ```

3. **Run a full self-audit**

   ```bash
   make audit
   ```

4. **Human-in-the-Loop (CLI)** — `core-admin` is your primary tool for guiding the system.

   **Creating New Projects**

   ```bash
   # Create a new, governed application using a starter kit
   core-admin new my-new-app --profile default
   ```

   **Onboarding Existing Projects**

   ```bash
   # Analyze an existing repo and propose a starter constitution
   core-admin byor-init /path/to/existing-repo
   ```

   **Managing the Constitution**

   ```bash
   # List pending constitutional changes
   core-admin proposals-list

   # Sign a proposal with your key
   core-admin proposals-sign cr-example.yaml

   # Approve a proposal (runs a canary self-audit)
   core-admin proposals-approve cr-example.yaml
   ```

   > If `core-admin` isn’t found, prefix with: `poetry run core-admin ...`

---

## 🌱 Contributing

We welcome contributions from AI engineers, DevOps pros, and governance experts.

* See **CONTRIBUTING.md** to get started.
* Check the **Project Roadmap** for where we're headed: `docs/04_ROADMAP.md`.

---

## 📄 License

Licensed under the **MIT License**. See `LICENSE`.

\--- END OF FILE ./README.md ---

\--- START OF FILE ./docs/04\_ROADMAP.md ---

# 4. The CORE Project Roadmap

## Preamble: From Foundation to Future

The initial development of CORE focused on building a stable, self-aware, and constitutionally governed foundation. That foundational work established our current stable state and is now considered complete. A historical record of that process can be found in `docs/archive/StrategicPlan.md`.

**This document outlines our current and future direction.** With a stable and secure foundation in place, the project is now moving into its next major phase: **enabling true autonomous application development.**

The following sections outline the key architectural challenges and features on our roadmap. We welcome discussion and contributions on these topics.

---

## Phase 1: Scaling the Constitution

As identified in our external architectural reviews, the current constitutional structure, while sound, faces several scalability challenges. Our next priority is to evolve the `.intent/` directory to support a system that can manage hundreds or thousands of files.

### 1.1: Implement Modular Manifests

* **Status:** ⏳ Not Started

### 1.2: Implement Hierarchical Capabilities

* **Status:** ⏳ Not Started

### 1.3: Implement Hierarchical Domains

* **Status:** ⏳ Not Started

---

## Phase 2: Enhancing Agent Reasoning

The next step is to make the system's AI agents smarter and safer in how they interpret and act upon the constitution.

### 2.1: Implement a Precedence of Principles

* **Status:** ⏳ Not Started

### 2.2: Enforce Auditable Justification Logs

* **Status:** ⏳ Not Started

---

## Phase 3: Autonomous Application Generation

This is the ultimate goal of the CORE project. With a scalable constitution and smarter agents, we will build the capabilities for CORE to generate and manage new software projects from a high-level intent.

* **Status:** ⏳ Not Started

---

## Phase 4: Constitutional Self-Improvement

This phase focuses on enabling CORE to reason about and improve its own "Mind". The goal is to build meta-capabilities that allow the system to use external intelligence to enhance its own governance.

### 4.1: Implement Constitutional Peer Review

* **Status:** ✅ Complete. The `review export` and `review peer-review` commands are implemented. The system can successfully use an external LLM to critique its own constitution.

### 4.2: Implement Content Drift Detection

* **Status:** ⏳ Not Started

---

## Phase 5: Achieving Operational Robustness

This new phase, based on feedback from the AI Peer Review Board, focuses on adding the critical policies and procedures required for real-world operation and enterprise-grade governance.

### 5.1: Formalize Enforcement Levels

* **Challenge:** The terms "soft" and "hard" enforcement are ambiguous.
* **Goal:** Create a new policy file (`.intent/policies/enforcement_model.yaml`) that formally defines the behavior of each enforcement level, ensuring consistent and predictable governance.
* **Status:** ⏳ Not Started

### 5.2: Implement Critical Operational Policies

* **Challenge:** The constitution lacks policies for critical real-world operations.
* **Goal:** Create a series of new policy files to govern Data Privacy, Secrets Management, Incident Response, and External Dependency Management.
* **Status:** ⏳ Not Started

### 5.3: Define Human Operator Lifecycle

* **Challenge:** The process for managing human approvers is not fully documented.
* **Goal:** Expand `.intent/constitution/approvers.yaml` or create a new procedure document that defines the formal process for onboarding, offboarding, and key rotation/revocation for human operators.
* **Status:** ⏳ Not Started

---

## Phase 6: Improving Architectural Health (New)

This phase addresses technical debt identified by the `ConstitutionalAuditor` to ensure the long-term health and maintainability of the codebase, upholding the `separation_of_concerns` principle.

### 6.1: Refactor `codegraph_builder.py`

* **Challenge:** The `KnowledgeGraphBuilder` class has grown too large (304 LLOC) and mixes responsibilities (file discovery, AST parsing, domain mapping, pattern matching).
* **Goal:** Decompose `KnowledgeGraphBuilder` into smaller, single-responsibility helper classes or modules. For example, a `PatternMatcher` class, a `DomainResolver` class, and a `SymbolParser` class.
* **Status:** ⏳ Not Started

### 6.2: Refactor `proposal_checks.py`

* **Challenge:** The `ProposalChecks` class is becoming a complexity outlier (190 LLOC).
* **Goal:** Refactor the large check methods into smaller, more focused helper functions to improve readability and testability.
* **Status:** ⏳ Not Started

