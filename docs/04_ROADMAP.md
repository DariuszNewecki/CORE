# 4. The CORE Project Roadmap

## Preamble: From Foundation to Reason

The initial development of CORE (up to and including the `v0.2.0` release) focused on building a stable, self-aware, and constitutionally governed foundation. That foundational work is now considered complete. A historical record of that process can be found in `docs/archive/StrategicPlan.md`.

**This document outlines our new, singular direction.** With a stable foundation in place, the project is moving into its next major phase: **evolving from a system with hardcoded logic to a true reasoning system built on the Mind/Body/Will architecture.**

Our entire development effort is now focused on the epic described below.

---

## The `v1.0` Epic: Implementing the Mind/Body/Will Trinity

**GitHub Epic:** [epic: Refactor to a Policy-Driven Cognitive Layer (Mind/Body/Will)](https://github.com/DariuszNewecki/CORE/issues/43)

**Goal:** To fundamentally refactor CORE's architecture to recognize the LLM layer as the system's "Will." We will replace the hardcoded `OrchestratorClient` and `GeneratorClient` with a policy-driven, role-based system for selecting and using cognitive resources.

### Phase 1: Amend the Constitution (The Mind)
-   **Challenge:** The system's cognitive capabilities are implicitly defined in Python code.
-   **Goal:** Create a new constitutional file, `.intent/knowledge/cognitive_roles.yaml`, to explicitly define the reasoning agents (e.g., `Planner`, `Coder`, `SecurityAnalyst`) and the models that power them.
-   **Status:** ⏳ **Not Started**

### Phase 2: Evolve the Machinery (The Body)
-   **Challenge:** The Body currently contains logic for choosing and calling LLMs.
-   **Goal:** Create a new, simple `CognitiveService` in the `core` domain. Its only job is to read `cognitive_roles.yaml` and provide a configured client for a requested role. All complex reasoning is removed from the Body.
-   **Status:** ⏳ **Not Started**

### Phase 3: Adapt the Agents (The Will)
-   **Challenge:** The system's agents directly instantiate specific clients.
-   **Goal:** Refactor all agentic processes (e.g., `run_development_cycle`) to use the new `CognitiveService`. The agent's logic will be simplified to: "I need to perform a `planning` task, please give me a client for the `Planner` role."
-   **Status:** ⏳ **Not Started**

### Phase 4: Deprecate and Remove (Cleanup)
-   **Challenge:** The old client classes and configurations will become obsolete.
-   **Goal:** Once all agents are migrated, completely remove the old `OrchestratorClient` and `GeneratorClient` classes and update `runtime_requirements.yaml` to reflect the new, more generic configuration.
-   **Status:** ⏳ **Not Started**

---

## Historical Roadmap (Completed in v0.2.0)

The following goals were part of the initial push to create a stable foundation and are now complete.

*   **Phase: Scaling the Constitution** (✅ Complete)
*   **Phase: Autonomous Application Generation (MVP)** (✅ Complete)
*   **Phase: Constitutional Self-Improvement (Peer Review)** (✅ Complete)
*   **Phase: Achieving Operational Robustness** (🚧 In Progress -> Completed in v0.2.0)
*   **Phase: Improving Architectural Health** (🚧 In Progress -> Completed in v0.2.0)