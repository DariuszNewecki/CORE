# Conversational Flow – Current Functional State

## Purpose

This document describes the **current, observable conversational behavior of CORE** as implemented today.

It is intentionally factual and non-aspirational. The goal is to establish a reliable baseline for governance, auditing, and future evolution.

If there is a discrepancy between this document and the code, **the code is considered the source of truth** and this document must be updated accordingly.

---

## 1. Conversational Entry Points

### 1.1 Primary Entry Point(s)

* CLI-driven interaction (via `core`, not `core-admin`)

### 1.2 Secondary / Implicit Entry Points

* None explicitly defined at this stage

### 1.3 Invocation Context

* User-triggered, synchronous execution
* No background or autonomous conversational loops

---

## 2. High-Level Execution Flow (As Implemented)

The current conversational flow follows this simplified sequence:

1. User input is received via CLI
2. Minimal system context is constructed
3. Input is passed to the LLM routing and execution layer
4. LLM response is returned directly to the user

No explicit intermediate orchestration layers are exposed yet.

---

## 3. Context Construction (Current Behavior)

### 3.1 Context Inputs Used

* Static system prompt (implicit)
* User-provided message (current turn only)

### 3.2 Context Inputs Not Used

* Conversational history beyond the current turn
* Constitution summaries (explicit injection)
* Standards or policy excerpts
* Symbol or capability expansion
* Vector-based memory (Qdrant)

### 3.3 Context Assembly Discipline

* Context assembly is implicit and minimal
* No formal context bundle schema exists yet

---

## 4. Intent Handling

### 4.1 Explicit Intent Routing

* None

### 4.2 Implicit Intent Assumptions

* All user input is treated as a general informational request

### 4.3 Governance Implications

* Intent classification is currently coarse-grained
* No explicit intent refusal or scoping logic exists

---

## 5. LLM Invocation

### 5.1 Model Selection

* Delegated to the existing LLM router
* Model choice is policy- and cost-aware

### 5.2 Prompt Structure

* System prompt + user message
* No structured role separation beyond this

### 5.3 Execution Guarantees

* Deterministic routing, non-deterministic reasoning
* No post-execution validation layer

---

## 6. Output Handling

### 6.1 Output Processing

* Raw LLM response returned to user

### 6.2 Output Validation

* None

### 6.3 Formatting

* CLI-default formatting

---

## 7. State and Memory

### 7.1 Ephemeral State

* Exists only for the duration of the CLI invocation

### 7.2 Durable State

* None

### 7.3 Persistence

* No conversational artifacts are persisted

---

## 8. Failure Modes and Limitations

### 8.1 Known Limitations

* No explicit intent routing
* No governed refusal semantics
* No conversational memory
* No structured context model

### 8.2 Failure Handling

* Errors surface directly to the CLI
* No retry or fallback at the conversational layer

---

## 9. Compliance with Target Architecture

### 9.1 Implemented Phases

* Input reception
* LLM execution

### 9.2 Partially Implemented Phases

* Context construction (minimal, implicit)

### 9.3 Missing Phases

* Explicit intent routing
* Governed refusal handling
* Post-execution validation
* State persistence

---

## 10. Summary

CORE currently supports a **minimal but functional conversational loop**:

* User input → LLM response

This establishes end-to-end viability but lacks explicit governance, intent attribution, and state awareness at the conversational layer.

All future conversational enhancements should be evaluated against both:

* this document (current reality), and
* the Conversational Flow Target Architecture (directional model).
