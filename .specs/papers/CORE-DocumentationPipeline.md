---
kind: paper
id: CORE-DocumentationPipeline
title: CORE — Documentation Pipeline
status: canonical
doctrine_tier: informational
---

<!-- path: .specs/papers/CORE-DocumentationPipeline.md -->

# CORE — Documentation Pipeline

**Status:** Canonical
**Authority:** Policy
**Scope:** Autonomous docstring detection and generation

---

## 1. Purpose

This paper defines the Documentation Pipeline — the two-worker sequence
responsible for detecting symbols with missing or degraded documentation and
writing governed docstrings to source files.

---

## 2. Pipeline Status

**Paused.** Both stages depend on a local LLM (`llm.local`) for reasoning.
`DocWorker` invokes `LocalCoder` via `cognitive_service` for docstring
generation. The pipeline is held until Ollama reasoning models are operational
alongside embeddings. Activate by flipping both YAMLs from `paused` to `active`
when local LLM reasoning is available (see ADR-024).

---

## 3. The Pipeline

### Stage 1 — Detection

**Worker:** `DocWorker`
**Declaration:** `.intent/workers/doc_worker.yaml`
**Class:** acting

Scans `src/**/*.py` for public symbols with missing or degraded documentation.
For each gap, invokes `LocalCoder` via `cognitive_service` to generate a
candidate docstring. Posts a `write.docstring` finding to the Blackboard with
the proposed docstring in the payload.

### Stage 2 — Writing

**Worker:** `DocWriter`
**Declaration:** `.intent/workers/doc_writer.yaml`
**Class:** acting

Consumes `write.docstring` findings from the Blackboard. Writes the proposed
docstring into the target source file via the `file.tag_metadata` action.

`DocWriter` may only mutate docstrings. It may not alter executable code. All
writes must pass the `WRITE_METADATA` semantic preservation proof enforced by
`file.tag_metadata`.

---

## 4. Blackboard Contract

| Subject prefix | Entry type | Producer | Consumer |
|---|---|---|---|
| `write.docstring` | finding | `DocWorker` | `DocWriter` |

---

## 5. Constitutional Identity

| Field | DocWorker | DocWriter |
|---|---|---|
| Declaration | `.intent/workers/doc_worker.yaml` | `.intent/workers/doc_writer.yaml` |
| Class | acting | acting |
| Phase | runtime | execution |
| Approval required | false | false |
| LLM | `llm.local` | none |

---

## 6. Responsibility Boundary

This pipeline governs:
- Detection of symbols missing or carrying degraded docstrings.
- Generation of candidate docstrings grounded in code and constitutional intent.
- Writing those docstrings into source files via the governed metadata path.

This pipeline does not govern:
- Docstring quality standards or style guidelines.
- Which symbols require documentation (that is a rule declaration decision).
- Test documentation or non-Python files.

---

## 7. Non-Goals

This paper does not define:
- the local LLM prompt used for docstring generation
- the criteria for "degraded" documentation quality
- how `file.tag_metadata` enforces the `WRITE_METADATA` proof

---

## 8. Amendment Discipline

This paper may be amended only by explicit constitutional replacement, in
accordance with the CORE amendment mechanism.

## Note 2026-10-10 — CCC run 6558a043 triage (proposal 0011)

> §3's Stage 2 actor is out of date. The `DocWriter` worker and `.intent/workers/doc_writer.yaml` (and `DocWorker`)
> were retired by ADR-048 D3. Docstring insertion is live through the `fix.docstrings` action, routed from
> `purity.docstrings.required` (ACTIVE, `auto_remediation.yaml`); the rule `metadata.operations.docstring_insert`
> permits it ("WRITE_METADATA actions MAY insert docstrings"). The constraint that this stage mutates docstrings
> only, never executable code, stands.
