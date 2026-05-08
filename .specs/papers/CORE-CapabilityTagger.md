<!-- path: .specs/papers/CORE-CapabilityTagger.md -->

# CORE — Capability Tagger

**Status:** Canonical
**Authority:** Policy
**Scope:** Autonomous capability-key assignment for public symbols

---

## 1. Purpose

This paper defines the `CapabilityTaggerWorker` — the sensing Worker responsible
for assigning capability keys to public symbols in the knowledge graph.

---

## 2. Problem Statement

CORE's capability taxonomy requires that every public symbol carry a capability
key classifying its function. Symbols lacking this key are invisible to
capability-based routing and analysis. Assigning keys manually across a
codebase of this scale is not tractable. `CapabilityTaggerWorker` automates
detection and classification using local LLM inference.

---

## 3. Definition

`CapabilityTaggerWorker` is a sensing Worker. It queries the knowledge graph for
public symbols with no assigned capability key, generates suggestions via
`CapabilityTaggerAgent` using a local LLM, and persists the assignments to the
database. It makes no file writes and produces no Blackboard findings — its
output is a direct knowledge-graph mutation.

---

## 4. Constitutional Identity

| Field | Value |
|---|---|
| Declaration | `.intent/workers/capability_tagger.yaml` |
| Class | `sensing` |
| Phase | `audit` |
| Permitted tools | `llm.local` |
| Approval required | false |
| Schedule | max_interval 3600 s |

---

## 5. Pipeline Status

**Paused.** Requires Ollama local LLM (`llm.local`) for reasoning tasks.
`CapabilityTaggerAgent` needs local inference for capability suggestions.
Activate when Ollama reasoning models are operational alongside embeddings
(see ADR-024).

---

## 6. Non-Goals

This paper does not define:
- the capability taxonomy itself (see `CORE-Capability-Taxonomy.md`)
- how capability keys are used in routing or analysis downstream
- the quality threshold for a suggestion to be persisted

---

## 7. Amendment Discipline

This paper may be amended only by explicit constitutional replacement, in
accordance with the CORE amendment mechanism.
