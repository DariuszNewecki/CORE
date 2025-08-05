# 1. The CORE Philosophy

## Prime Directive

**CORE exists to transform human intent into complete, evolving software systems — without drift, duplication, or degradation.**

It does not merely generate code; it **governs**, **learns**, and **rewrites** itself under the authority of an explicit, machine-readable constitution. It is a system designed to build other systems, safely and transparently.

## The CORE Belief System

Our architecture is founded on a set of core beliefs about the future of software development:

1.  **Intent, Not Instructions:** Software development should be about declaring a desired outcome (`intent`), not writing a list of procedural steps (`instructions`).
2.  **Governance is a Feature:** In a world of autonomous AI agents, safety, alignment, and auditability are not afterthoughts—they are the primary features of a trustworthy system.
3.  **Code is a Liability:** All code must justify its existence. It must be traceable to a declared purpose, validated against constitutional principles, and be as simple as possible. Unnecessary or un-auditable code is a source of risk.
4.  **A System Must Know Itself:** To evolve safely, a system must have a deep and accurate understanding of its own structure, capabilities, and rules. Self-awareness (`introspection`) is the prerequisite for self-improvement.

## The Ten-Phase Loop of Reasoned Action

All autonomous actions in CORE are governed by a ten-phase loop. This structure ensures that every action is deliberate, justified, and validated. It prevents the system from taking impulsive or un-auditable shortcuts.

The phases are:

1.  **GOAL:** A high-level objective is received from a human operator.
    *(e.g., "Add cryptographic signing to the approval process.")*

2.  **WHY:** The system links the goal to a core constitutional principle.
    *(e.g., "This serves the `safe_by_default` principle.")*

3.  **INTENT:** The goal and its justification are formalized into a clear, machine-readable intent.
    *(e.g., Formalize the request into a plan to modify the `core-admin` tool.)*

4.  **AGENT:** The system selects the appropriate agent(s) for the task.
    *(e.g., The `PlannerAgent` is assigned.)*

5.  **MEANS:** The agent consults its capabilities and knowledge to determine *how* it can achieve the intent.
    *(e.g., The agent knows it has `code_generation` and `introspection` capabilities.)*

6.  **PLAN:** The agent produces a detailed, step-by-step, auditable plan.
    *(e.g., 1. Add `cryptography` library. 2. Add `keygen` function. 3. Modify `approve` function...)*

7.  **ACTION:** The system executes the plan, one validated step at a time.
    *(e.g., The `GeneratorAgent` writes new code to files.)*

8.  **FEEDBACK:** The system's "immune system" (`ConstitutionalAuditor`, `pytest`, linters) provides feedback on the action.
    *(e.g., "The new code fails a linting check." or "All tests pass.")*

9.  **ADAPTATION:** The system uses the feedback to self-correct or confirm the change.
    *(e.g., The `SelfCorrectionEngine` fixes the linting error, or `GitService` commits the successful change.)*

10. **EVOLUTION:** The system updates its self-image (`KnowledgeGraph`) to reflect its new state, completing the loop.

This loop ensures that CORE does not simply act, but *reasons*. Every change is a deliberate, auditable, and constitutionally-aligned evolution.