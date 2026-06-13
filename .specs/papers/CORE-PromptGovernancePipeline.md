---
kind: paper
id: CORE-PromptGovernancePipeline
title: CORE — Prompt Governance Pipeline
status: canonical
doctrine_tier: informational
---

<!-- path: .specs/papers/CORE-PromptGovernancePipeline.md -->

# CORE — Prompt Governance Pipeline

**Status:** Canonical
**Authority:** Policy
**Scope:** Autonomous migration of inline prompt strings to governed PromptModel artifacts

---

## 1. Purpose

This paper defines the four-stage Prompt Governance Remediation Pipeline —
the worker sequence responsible for detecting, extracting, materializing, and
rewriting direct LLM call sites so every prompt in CORE is governed as a named
PromptModel artifact.

---

## 2. Problem Statement

CORE's constitutional rules require that all LLM invocations go through
`PromptModel.invoke()` with a registered prompt artifact, not via inline
strings. Existing code written before this rule was enforced contains direct
`make_request_async()` calls with inline prompt strings. Migrating these sites
manually is error-prone and does not scale. The pipeline automates detection,
extraction, artifact creation, and call-site rewriting under full constitutional
governance.

---

## 3. Pipeline Status

**Paused.** All four stages are pending activation of the
`make_request_async()` → `PromptModel.invoke()` migration campaign. The
pipeline is constitutionally declared and implementations are available; no
stage is running as of this paper's authorship. Activate by flipping all four
worker YAMLs from `paused` to `active` when the campaign begins.

---

## 4. The Pipeline

### Stage 1 — Audit Ingestion

**Worker:** `AuditIngestWorker`
**Declaration:** `.intent/workers/audit_ingest_worker.yaml`
**Class:** sensing

Reads the most recent audit findings for rule `ai.prompt.model_required` and
posts each unprocessed violation as a Blackboard finding with subject
`audit.violation::ai.prompt.model_required::{file_path}`.

This is the sole entry point for `ai.prompt.model_required` findings. No
`ai.*`-namespace AuditViolationSensor exists for this rule; `AuditIngestWorker`
fills that role.

### Stage 2 — Prompt Extraction

**Worker:** `PromptExtractorWorker`
**Declaration:** `.intent/workers/prompt_extractor_worker.yaml`
**Class:** sensing

Consumes `ai.prompt.model_required` findings from the Blackboard. For each
unprocessed violation, reads the source file and extracts the inline prompt
string passed to `make_request_async()`. Invokes a local LLM for extraction
assistance. Posts an extracted prompt payload to the Blackboard for Stage 3.

### Stage 3 — Artifact Writing

**Worker:** `PromptArtifactWriter`
**Declaration:** `.intent/workers/prompt_artifact_writer.yaml`
**Class:** acting

Consumes approved prompt extraction findings from the Blackboard. For each
approved extraction, generates and writes the three PromptModel artifact files
to `var/prompts/`. Invokes `llm.architect` for artifact generation. Requires
human approval (`approval_required: true`) before any file write.

**Implementation note:** The Stage 3 implementation (`body.workers.prompt_artifact_writer`)
may be incomplete. Verify correctness before activating.

### Stage 4 — Call Site Rewriting

**Worker:** `CallSiteRewriter`
**Declaration:** `.intent/workers/call_site_rewriter.yaml`
**Class:** acting

Consumes `prompt.artifact` findings from the Blackboard. For each file with
approved prompt artifacts, rewrites the source file to replace
`make_request_async()` calls with `PromptModel.invoke()` calls via the full
Crate/Canary ceremony. Requires human approval (`approval_required: true`).
Implementation is complete.

---

## 5. Constitutional Identity

| Field | Stage 1 | Stage 2 | Stage 3 | Stage 4 |
|---|---|---|---|---|
| Worker | `AuditIngestWorker` | `PromptExtractorWorker` | `PromptArtifactWriter` | `CallSiteRewriter` |
| Class | sensing | sensing | acting | acting |
| Phase | audit | runtime | execution | execution |
| Approval required | false | false | **true** | **true** |
| LLM | none | `llm.local` | `llm.architect` | `llm.architect` |

---

## 6. Responsibility Boundary

This pipeline governs:
- Detection of `make_request_async()` call sites that violate `ai.prompt.model_required`.
- Extraction of inline prompt strings from those sites.
- Generation of governed PromptModel artifacts.
- Rewriting call sites to use the governed invocation path.

This pipeline does not govern:
- The correctness or quality of extracted prompts.
- Prompt artifact naming conventions beyond what PromptModel declares.
- Runtime behavior of the rewritten call sites.

---

## 7. Non-Goals

This paper does not define:
- the PromptModel artifact schema
- what constitutes a valid prompt extraction
- how `PromptModel.invoke()` is implemented

---

## 8. Amendment Discipline

This paper may be amended only by explicit constitutional replacement, in
accordance with the CORE amendment mechanism.
