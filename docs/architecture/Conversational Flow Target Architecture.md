# CORE – Conversational Flow Target Architecture

## 1. Purpose of This Document

This document defines the **target conversational architecture** for CORE. It captures how conversations are *conceptually* handled by the system once fully evolved, independent of current implementation constraints.

This document is **normative at the design level** but **non-prescriptive at the implementation level**. It serves as a long-term architectural anchor against which runtime behavior and future refactors must be evaluated.

---

## 2. Scope and Non-Scope

### In Scope

* Conceptual definition of a "conversation" in CORE
* The phases a conversational interaction passes through
* The responsibilities involved in handling conversations
* Governance and constitutional constraints applicable to conversations

### Explicitly Out of Scope

* File paths, class names, or module structures
* UI / UX considerations
* Prompt engineering details
* Model-specific behavior
* Short-term MVP shortcuts

---

## 3. Definition: Conversation in CORE

In CORE, a conversation is a **governed execution cycle**, not a free-form dialogue.

A conversation is defined as:

> A bounded interaction sequence where user input is interpreted, evaluated against governance constraints, routed through allowed capabilities, executed via the Will (LLM), and optionally committed to system state.

Key properties:

* Conversations are **purpose-driven**, not open-ended
* Every response is attributable to an explicit intent
* Conversations must converge, not drift

---

## 4. High-Level Conversational Phases

Every conversational interaction follows the same conceptual phases:

1. **Input Reception**
   User-provided message and metadata are accepted by the system.

2. **Context Construction**
   A bounded, governed context is assembled from allowed sources.

3. **Intent Identification and Routing**
   The system determines what *kind* of action is being requested and whether it is allowed.

4. **Execution via the Will**
   An LLM is invoked with a fully prepared and constrained prompt.

5. **Post-Execution Handling**
   Output is validated, formatted, and optionally persisted.

6. **State Update**
   Conversational or system state is updated where appropriate.

These phases are mandatory and must not be collapsed or bypassed.

---

## 5. Core Conversational Responsibilities

This section defines **responsibility roles**, not concrete components.

### 5.1 Conversation Orchestrator

* Coordinates the conversational phases
* Owns flow control
* Performs no reasoning or policy interpretation

### 5.2 Context Builder

* Assembles conversational context deterministically
* Selects from allowed sources only
* Never invents or improvises context

### 5.3 Intent Router

* Maps natural language input to:

  * Intent class
  * Capability label set
  * Execution mode
* Enforces constitutional and standard constraints
* Produces explainable routing decisions

### 5.4 Will (LLM Execution Layer)

* Executes tasks based on prepared prompts
* Performs non-deterministic reasoning only
* Is forbidden from:

  * Re-routing intent
  * Expanding scope
  * Violating governance

### 5.5 Conversation State Management

* Separates ephemeral conversational state from durable system artifacts
* Ensures only validated outcomes affect the Mind

---

## 6. Governance and Constitutional Constraints

Conversational flow is subject to the same governance principles as all CORE behavior.

Key constraints:

* No capability may be invoked unless explicitly allowed
* Capability labels (`symbols.key`) represent **what may be done**, not identities
* The Constitution and Standards are always higher authority than conversational intent
* Refusals must be structured and attributable

---

## 7. Memory and State Boundaries

CORE distinguishes between:

### 7.1 Ephemeral Conversational State

* Recent turns
* Active intent
* Pending clarifications

### 7.2 Durable Conversational Artifacts

* Accepted proposals
* Decisions
* Governance-relevant outputs

Only durable artifacts may influence long-term system state.

---

## 8. Failure and Refusal Semantics

Not all conversational inputs result in execution.

Valid non-success outcomes include:

* Governed refusal (policy violation)
* Request for clarification (insufficient intent)
* Scoped limitation (partial allowance)

Failures must:

* Be explicit
* Be explainable
* Never degrade into hallucination

---

## 9. Directional Guarantees

Any future conversational implementation must:

* Preserve the phase structure defined here
* Maintain explicit intent attribution
* Reduce ambiguity over time
* Move closer to this model, never sideways

This document is the reference point for evaluating that direction.

---

## 10. Relationship to Current Implementation

This document does **not** claim that the current system fully implements this model.

Instead, it defines:

* The target state
* The architectural invariants
* The criteria against which incremental improvements are judged

Implementation reality must be documented separately and reconciled against this model.
