# Conversations – Runtime Documentation

## Purpose

This directory documents **how conversational interactions are handled at runtime in CORE**.

These documents describe **what the system actually does today**, not what it is intended to do in the future. They are deliberately factual, versioned alongside the codebase, and expected to evolve over time.

This folder exists to prevent drift between:

* architectural intent,
* implementation reality, and
* developer understanding.

---

## Position in the Documentation Landscape

The documentation in this folder is **operational**, not constitutional.

| Document Type           | Authority             | Change Rate | Location              |
| ----------------------- | --------------------- | ----------- | --------------------- |
| Constitutional / Intent | Design law            | Very low    | `.intent/`            |
| Target Architecture     | Directional invariant | Low         | Design docs           |
| Conversational Runtime  | Implementation truth  | Medium      | `docs/conversations/` |

If there is a conflict:

* Constitution overrides everything
* Target Architecture defines direction
* Runtime docs describe reality

---

## What Belongs Here

Documents in this directory MUST:

* Describe existing behavior
* Reflect what is observable in the code
* Explicitly call out limitations or shortcuts
* Avoid aspirational or speculative language

Typical contents include:

* Conversational entry points
* Actual execution flow
* Context construction as implemented
* Intent handling as implemented
* LLM invocation mechanics
* State and memory behavior

---

## What Does *Not* Belong Here

The following must NOT be placed in this directory:

* Constitutional rules or standards
* Design proposals or future architectures
* Prompt experiments
* Model-specific tuning notes
* UX or presentation concerns

Those belong elsewhere and are governed differently.

---

## Expected Files

This directory is expected to contain, at minimum:

* `CURRENT_STATE.md`
  Describes the current end-to-end conversational flow as implemented.

* `GAP_ANALYSIS.md` *(added later)*
  Maps current behavior against the target conversational architecture.

Additional files may be added as conversational capabilities evolve, provided they remain factual and scoped.

---

## Update Discipline

Any change that alters conversational behavior MUST be accompanied by an update to the relevant document in this folder.

This is a deliberate governance rule:

> If behavior changes but documentation does not, the change is incomplete.

---

## Relationship to Target Architecture

The **Conversational Flow Target Architecture** defines where CORE is heading.

The documents in this folder define where CORE currently stands.

Progress is measured by **closing the gap between the two**, not by adding features in isolation.
