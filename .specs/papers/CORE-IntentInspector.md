<!-- path: .specs/papers/CORE-IntentInspector.md -->

# CORE — Intent Inspector

**Status:** Canonical
**Authority:** Policy
**Scope:** Constitutional self-audit of the `.intent/` layer

---

## 1. Purpose

This paper defines the `IntentInspector` — the sensing Worker that audits the
quality of CORE's own governance layer. The Intent Inspector turns the
constitutional audit instrument inward.

---

## 2. Problem Statement

The audit sensors verify that `src/` code complies with `.intent/`. Nothing
verifies that `.intent/` itself is well-formed, coherent, and internally
consistent. A governance document that references a non-existent worker, an
orphaned rule that no worker enforces, or a paper whose narrative contradicts
its declarations — these are governance failures that the standard audit loop
cannot detect because it reads `.intent/` as authoritative input, not as subject.
`IntentInspector` makes `.intent/` auditable.

---

## 3. Definition

`IntentInspector` is a sensing Worker. It runs three passes over `.intent/`
and posts all findings to the Blackboard. It makes no changes to any governance
document or source file.

---

## 4. Constitutional Identity

| Field | Value |
|---|---|
| Declaration | `.intent/workers/intent_inspector.yaml` |
| Class | `sensing` |
| Phase | `runtime` |
| Permitted tools | `llm.local` |
| Approval required | false |

---

## 5. Inspection Passes

**Pass 1 — Structural**
Pure Python scan. Verifies that every `.intent/` document has required fields
and a `$schema` reference. No LLM required. Detects structural malformation
that would prevent the governance layer from loading correctly.

**Pass 2 — Coherence**
LLM-assisted. For each document, asks whether the narrative is clear,
internally consistent, and accurately describes what the document declares.
Posts a finding per document where narrative and declarations diverge.

**Pass 3 — Alignment**
LLM-assisted. Detects cross-document conflicts, orphaned declarations, and
rules that reference non-existent workers, files, or roles. Identifies
declarations that are constitutionally inconsistent with each other.

All three passes must be operational together. The structural pass could run
standalone, but the worker is held until all three can operate as a unit.

---

## 6. Pipeline Status

**Paused.** Passes 2 and 3 invoke `qwen2.5:7b` via `cognitive_service` for
coherence and alignment reasoning. The worker is held until Ollama reasoning
models are operational alongside embeddings (see ADR-024).

---

## 7. Responsibility Boundary

This worker governs:
- Structural validity of `.intent/` documents.
- Narrative coherence of individual governance documents.
- Cross-document alignment and orphan detection.

This worker does not govern:
- `src/` code compliance (that is the AuditViolationSensor's domain).
- `.specs/` documents.
- Automated remediation of governance findings (detection only).

---

## 8. Non-Goals

This paper does not define:
- what constitutes acceptable coherence quality
- how governance findings are routed to remediation
- the LLM prompt used for coherence and alignment passes

---

## 9. Amendment Discipline

This paper may be amended only by explicit constitutional replacement, in
accordance with the CORE amendment mechanism.
