# 4. The CORE Project Roadmap

## Preamble: From Foundation to Future

The initial development of CORE focused on building a stable, self-aware, and constitutionally governed foundation. That foundational work established our current stable state and is now considered complete. A historical record of that process can be found in `docs/archive/StrategicPlan.md`.

**This document outlines our current and future direction.** With a stable and secure foundation in place, the project is now moving into its next major phase: **enabling true autonomous application development.**

The following sections outline the key architectural challenges and features on our roadmap. We welcome discussion and contributions on these topics.

---

## Phase 1: Scaling the Constitution

As identified in our external architectural reviews, the current constitutional structure, while sound, faces several scalability challenges. Our next priority is to evolve the `.intent/` directory to support a system that can manage hundreds or thousands of files.

### 1.1: Implement Modular Manifests
-   **Status:** ⏳ **Not Started**

### 1.2: Implement Hierarchical Capabilities
-   **Status:** ⏳ **Not Started**

### 1.3: Implement Hierarchical Domains
-   **Status:** ⏳ **Not Started**

---

## Phase 2: Enhancing Agent Reasoning

The next step is to make the system's AI agents smarter and safer in how they interpret and act upon the constitution.

### 2.1: Implement a Precedence of Principles
-   **Status:** ⏳ **Not Started**

### 2.2: Enforce Auditable Justification Logs
-   **Status:** ⏳ **Not Started**

---

## Phase 3: Autonomous Application Generation

This is the ultimate goal of the CORE project. With a scalable constitution and smarter agents, we will build the capabilities for CORE to generate and manage new software projects from a high-level intent.
-   **Status:** ⏳ **Not Started**

---

## Phase 4: Constitutional Self-Improvement

This phase focuses on enabling CORE to reason about and improve its own "Mind". The goal is to build meta-capabilities that allow the system to use external intelligence to enhance its own governance.

### 4.1: Implement Constitutional Peer Review
-   **Status:** ✅ **Complete.** The `review export` and `review peer-review` commands are implemented. The system can successfully use an external LLM to critique its own constitution.

### 4.2: Implement Content Drift Detection
-   **Status:** ⏳ **Not Started**

---

## Phase 5: Achieving Operational Robustness

This phase, based on feedback from the AI Peer Review Board, focuses on adding the critical policies and procedures required for real-world operation and enterprise-grade governance.

### 5.1: Formalize Enforcement Levels
-   **Challenge:** The terms "soft" and "hard" enforcement are ambiguous.
-   **Goal:** Create a new policy file (`.intent/policies/enforcement_model.yaml`) that formally defines the behavior of each enforcement level, ensuring consistent and predictable governance.
-   **Status:** ⏳ **Not Started**

### 5.2: Implement Critical Operational Policies
-   **Challenge:** The constitution lacks policies for critical real-world operations.
-   **Goal:** Formalize policies for **Data Privacy** (minimization, erasure, encryption), **Secrets Management**, **Incident Response**, and **External Dependency Management** (licensing, vulnerabilities).
-   **Status:** 🚧 **In Progress.** Secrets, Incident Response, and Dependency Management policies have been defined. Auditor checks are pending.

### 5.3: Define Human Operator Lifecycle
-   **Status:** ✅ **Complete.** This was addressed by creating `operator_lifecycle.md` and updating `approvers.yaml`.

---

## Phase 6: Improving Architectural Health

This phase addresses technical debt identified by the `ConstitutionalAuditor` to ensure the long-term health and maintainability of the codebase, upholding the `separation_of_concerns` principle.

### 6.1: Refactor `codegraph_builder.py`
-   **Challenge:** The `KnowledgeGraphBuilder` class has grown too large and mixes responsibilities.
-   **Goal:** Decompose `KnowledgeGraphBuilder` into smaller, single-responsibility helper classes or modules.
-   **Status:** ⏳ **Not Started**

### 6.2: Refactor `proposal_checks.py`
-   **Challenge:** The `ProposalChecks` class is becoming a complexity outlier.
-   **Goal:** Refactor the large check methods into smaller, more focused helper functions to improve readability and testability.
-   **Status:** ⏳ **Not Started**

---

## Phase 7: Agentic Self-Improvement

This phase focuses on evolving CORE's agents to be more autonomous and resilient by teaching them to handle common development friction and failures without human intervention.

### 7.1: Implement Autonomous Formatting & Linting Fixes
-   **Challenge:** The system's agents can generate code that violates formatting or linting rules, requiring human intervention to fix. This represents an incomplete `ADAPTATION` loop.
-   **Goal:** Enhance the agent execution loop to automatically apply formatting and auto-fixable linting changes to any generated code before it is written to disk.
-   **Status:** ⏳ **Not Started**

---

## Phase 8: Enterprise Readiness (New)

This phase, based on feedback from the AI Peer Review Board, focuses on adding policies and documentation required for enterprise-grade operation.

### 8.1: Define a Formal Testing Policy
-   **Challenge:** Testing standards are not formally defined in the constitution.
-   **Goal:** Create a new policy file governing test coverage requirements, data management, and mocking strategies.
-   **Status:** ⏳ **Not Started**

### 8.2: Define Formal Documentation Standards
-   **Challenge:** Documentation quality is a principle, but the standards are not explicit.
-   **Goal:** Create a new policy defining minimum documentation requirements for capabilities and a style guide for docstrings.
-   **Status:** ⏳ **Not Started**

### 8.3: Define Error Recovery Procedures
-   **Challenge:** Procedures for recovering from a corrupted state are not documented.
-   **Goal:** Create a formal document outlining procedures for automatic rollback scenarios and constitutional crisis resolution.
-   **Status:** ⏳ **Not Started**