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

-   **Challenge:** The current `project_manifest.yaml` is monolithic. At scale, this becomes a bottleneck and a single point of failure.
-   **Goal:** Refactor the system to support **domain-specific manifests** (e.g., `src/agents/manifest.yaml`). A master process will aggregate these into a global view, but day-to-day management will become modular.
-   **Status:** ⏳ **Not Started**

### 1.2: Implement Hierarchical Capabilities

-   **Challenge:** The current `capability_tags.yaml` is a flat list. This will become unmanageable as the system's skills grow.
-   **Goal:** Evolve the capability system to support **namespacing and hierarchy**. This will allow for a more organized and expressive taxonomy of actions (e.g., `data.storage.write`, `ui.render.table`).
-   **Status:** ⏳ **Not Started**

### 1.3: Implement Hierarchical Domains

-   **Challenge:** The architectural domains in `source_structure.yaml` are flat. Real-world applications require nested and layered architectures.
-   **Goal:** Evolve the domain model to support **parent-child relationships**, allowing domains to inherit permissions and creating a true architectural tree.
-   **Status:** ⏳ **Not Started**

---

## Phase 2: Enhancing Agent Reasoning

The next step is to make the system's AI agents smarter and safer in how they interpret and act upon the constitution.

### 2.1: Implement a Precedence of Principles

-   **Challenge:** AI agents lack the intuition to resolve conflicts between high-level principles (e.g., `clarity_first` vs. `safe_by_default`).
-   **Goal:** Create a new constitutional file that defines a **clear hierarchy or weighting system** for principles. This will provide agents with a deterministic framework for making decisions when rules conflict.
-   **Status:** ⏳ **Not Started**

### 2.2: Enforce Auditable Justification Logs

-   **Challenge:** An agent's "reasoning" for a particular plan can be opaque.
-   **Goal:** Modify the `PlannerAgent` to require that every generated plan includes a **`justification` block**. This block will explicitly state which constitutional principle the plan serves and provide a brief, human-readable explanation of the agent's reasoning. This log will become a critical part of the audit trail.
-   **Status:** ⏳ **Not Started**

---

## Phase 3: Autonomous Application Generation

This is the ultimate goal of the CORE project. With a scalable constitution and smarter agents, we will build the capabilities for CORE to generate and manage new software projects from a high-level intent.

-   **Goal:** Develop the end-to-end flow where a user can provide a prompt like, "Build a simple web app to track my book collection," and have CORE:
    1.  Propose a new constitutional structure for the book app.
    2.  Generate the initial code, including models, API endpoints, and basic UI.
    3.  Continuously run its self-audit against the new application.
    4.  Accept further intents to evolve the new application.
-   **Status:** ⏳ **Not Started**

---

## Phase 4: Constitutional Self-Improvement

This phase focuses on enabling CORE to reason about and improve its own "Mind". The goal is to build meta-capabilities that allow the system to use external intelligence to enhance its own governance.

### 4.1: Implement Constitutional Peer Review

-   **Challenge:** The system's own "Mind" (`.intent/`) can suffer from incompleteness or lack of clarity that its own internal checks cannot detect.
-   **Goal:** Implement the **Constitutional Peer Review Loop**. This involves:
    1.  Creating a `ReviewerAgent`.
    2.  Building the `export_constitution` capability to bundle the `.intent/` directory for analysis.
    3.  Implementing the `constitutional_peer_review` capability, which sends the bundle to an external LLM for critique.
    4.  The agent will then parse the feedback and autonomously create a formal proposal (`cr-*.yaml`) with suggested improvements to its own constitution.
-   **Status:** ⏳ **Not Started**

### 4.2: Implement Content Drift Detection

-   **Challenge:** The system cannot currently detect content duplication in non-code files (e.g., YAML templates), which violates the `single_source_of_truth` principle.
-   **Goal:** Build the `audit.check.content_drift` capability. This will involve:
    1.  Creating a new manifest file (`.intent/knowledge/content_invariants.yaml`) where content equivalences can be declared.
    2.  Implementing a new check in the `ConstitutionalAuditor` that verifies the content of these designated files are identical.
-   **Status:** ⏳ **Not Started**

We believe that by solving the challenges in Phase 1 and 2, we will have built a foundation of trust and scalability that makes Phase 3 and 4 possible.
