# 1. The CORE Philosophy

## Prime Directive

**CORE exists to transform human intent into complete, evolving software systems — without drift, duplication, or degradation.**

It does not merely generate code; it **governs**, **learns**, and **rewrites** itself under the authority of an explicit, machine-readable constitution. It is a system designed to build other systems, safely and transparently.

---

## The Architectural Trinity: Mind, Body, and Will

Our architecture is founded on a strict separation of concerns that mirrors a reasoned entity. This trinity ensures that the system's intelligence is always governed by its principles, and its actions are always simple, auditable, and safe.

*   🏛️ **The Mind (`.intent/`):** The Constitution. A declarative, version-controlled collection of files representing the system's complete self-knowledge, purpose, and rules. It is the timeless source of truth for **what** the system should be and **why**.

*   🦾 **The Body (`src/`):** The Machinery. An imperative, executable collection of simple tools. Its capabilities are modest and reliable: writing files, running tests, parsing code. It handles the **how** of interacting with the world. We do not build smart tools; we build simple tools that a smart, constitutionally-bound Will can use.

*   🧠 **The Will (The LLM Layer):** The Reasoning. An orchestrated set of specialized AI cognitive roles. The Will is the dynamic, intelligent actor in the system. It is not part of the Body's code; it is the cognitive force that interprets the Mind's intent to wield the Body's tools.

---

## The Ten-Phase Loop of Reasoned Action

All autonomous actions in CORE are governed by a ten-phase loop. This structure ensures that every action is deliberate, justified, traceable, and validated against the constitution. It prevents the system from taking impulsive or un-auditable shortcuts.

1.  **GOAL:** A high-level objective is received from a human operator.
    *(e.g., "Add cryptographic signing to the approval process.")*

2.  **WHY:** The system's **Will** links the goal to a core principle in the **Mind**.
    *(e.g., "This serves the `safe_by_default` principle.")*

3.  **INTENT:** The goal and its justification are formalized into a clear, machine-readable intent.
    *(e.g., Formalize the request into a plan to modify the `core-admin` tool.)*

4.  **AGENT:** The **Will** selects the appropriate cognitive role(s) for the task.
    *(e.g., The `Planner` and `Coder` roles are assigned.)*

5.  **MEANS:** The selected agent consults the capabilities of the **Body**.
    *(e.g., The agent knows the Body has `code_generation` and `introspection` tools.)*

6.  **PLAN:** The agent produces a detailed, auditable plan.
    *(e.g., 1. Add `cryptography` library. 2. Add `keygen` function. 3. Modify `approve` function...)*

7.  **ACTION:** The **Will** commands the **Body** to execute the plan, one step at a time.
    *(e.g., The `FileHandler` tool writes new code to files.)*

8.  **FEEDBACK:** The **Body's** "immune system" (`ConstitutionalAuditor`, `pytest`) provides feedback.
    *(e.g., "The new code fails a linting check." or "All tests pass.")*

9.  **ADAPTATION:** The **Will** uses the feedback to self-correct or confirm the change.
    *(e.g., The `Refactorer` role fixes the linting error, or the `GitService` tool commits the successful change.)*

10. **EVOLUTION:** The **Mind** is updated (`KnowledgeGraph`) to reflect the new state, completing the loop.

This loop ensures that CORE does not simply act, but *reasons*. Every change is a deliberate, auditable, and constitutionally-aligned evolution.