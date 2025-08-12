# 4. The CORE Project Roadmap

## Preamble: From Foundation to Future

The initial development of CORE focused on building a stable, self-aware, and constitutionally governed foundation. The major phases of this foundational work are now complete, as documented in our **[Strategic Plan](StrategicPlan.md)**. That document tells the story of how we achieved our current stable state.

**This document outlines our future direction.** With a stable and secure foundation in place, the project is now moving into its next major phase: **enabling true autonomous application development.**

-   ✅ **A Unified "Mind":** The system's self-knowledge has been consolidated into a single, verifiable Knowledge Graph.
-   ✅ **A Unified Governance Engine:** The `ConstitutionalAuditor` is now the single, dynamic engine for enforcing all constitutional principles.
-   ✅ **Constitutional Compliance:** The system now passes its own strict self-audit with zero errors, proving its internal consistency.
-   ✅ **A Secure Amendment Process:** A robust, human-in-the-loop, cryptographically signed process for evolving the system's own constitution has been implemented and verified.

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

This new phase, based on feedback from the AI Peer Review Board, focuses on adding the critical policies and procedures required for real-world operation and enterprise-grade governance.

### 5.1: Formalize Enforcement Levels
-   **Challenge:** The terms "soft" and "hard" enforcement are ambiguous.
-   **Goal:** Create a new policy file (`.intent/policies/enforcement_model.yaml`) that formally defines the behavior of each enforcement level, ensuring consistent and predictable governance.
-   **Status:** ⏳ **Not Started**

### 5.2: Implement Critical Operational Policies
-   **Challenge:** The constitution lacks policies for critical real-world operations.
-   **Goal:** Create a series of new policy files to govern Data Privacy, Secrets Management, Incident Response, and External Dependency Management.
-   **Status:** ⏳ **Not Started**

### 5.3: Define Human Operator Lifecycle
-   **Challenge:** The process for managing human approvers is not fully documented.
-   **Goal:** Expand `.intent/constitution/approvers.yaml` or create a new procedure document that defines the formal process for onboarding, offboarding, and key rotation/revocation for human operators.
-   **Status:** ⏳ **Not Started**
