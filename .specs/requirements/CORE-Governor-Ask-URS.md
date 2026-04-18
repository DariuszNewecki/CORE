# CORE — Governor Interrogation Command
## User Requirements

**Status:** Draft
**Authority:** Policy
**Scope:** `core-admin ask` command
**Audience:** Governor (operator of CORE)
**Version:** 0.2
**Last updated:** 2026-04-17

---

## Change Log

| Version | Date | Change |
|---------|------|--------|
| 0.1 | 2026-04-17 | Initial draft, authored against existing `ai.prompt.*` governance. |
| 0.2 | 2026-04-17 | Corrected PromptModel artifact requirements to include `user.txt` per `ai.prompt.model_artifact_required` enforcement mapping. Clarified all three artifact files in deliverables and data sources. |

---

## 1. Purpose

The governor needs a single command that answers architectural and strategic
questions about CORE with full governance context automatically applied:

> **What should I do next? Why is this right? What am I missing?**

Today the governor reconstitutes context manually at the start of every
architectural reasoning session with an external LLM: constitutional
principles, specification retrieval, role contract, output shape. This
reconstitution is forgetful by construction. When a piece is omitted the
answer drifts, and the governor must detect and correct the drift in real
time. This is an ungoverned loop sitting above `.intent/`.

`core-admin ask` closes that loop. Context assembly, role enforcement,
output validation, and audit logging move from the governor's head into a
governed worker. The LLM becomes a component, not an oracle — the same
trust model CORE already applies to code generation, applied now to the
governor's own reasoning.

`core-admin runtime dashboard` tells the governor whether CORE needs them.
`core-admin ask` is how the governor reasons when the answer is yes.

---

## 2. The Core Requirement

The command must, for every question the governor asks, satisfy every item
below. No item is optional.

| # | Requirement | Enforced by |
|---|-------------|-------------|
| 1 | Invocation routes through an existing PromptModel artifact | `ai.prompt.model_required` |
| 2 | Manifest declares id, version, role, input, output, success_criteria | `ai.prompt.model_artifact_required`, `ai.prompt.artifact.required_fields` |
| 3 | Artifact contains all three required files (`model.yaml`, `system.txt`, `user.txt`); `system.txt` is non-empty and carries constitutional grounding; `user.txt` declares the input template | `ai.prompt.model_artifact_required`, `ai.prompt.system_prompt_required` |
| 4 | LLM response is validated against the output contract before return | `ai.prompt.output_validation_required` |
| 5 | Role is a declared cognitive role; no provider names leak into the artifact | `ai.prompt.artifact.role_abstraction`, `ai.prompt.artifact.no_provider_leak` |
| 6 | Relevant `.specs/`, rules, findings, and source retrieved per question | Worker composition |
| 7 | Every substantive claim in the answer labeled grounded or inferred | Output contract |
| 8 | Every grounded claim carries a citation to a verifiable artifact | Output contract |
| 9 | Unanswerable portions named explicitly, not improvised | Output contract |
| 10 | Retrieval-surfaced contradictions posted as blackboard findings | Worker behavior |
| 11 | Governor correction within a session triggers re-retrieval, not a new question | Worker behavior |
| 12 | Every session logged to the consequence log with full traceability | Worker behavior |

Items 1–5 are already governed by existing AI rules. This URS does not
introduce a new policy document; it specifies an artifact that conforms to
governance already in force. Items 6–12 are new behavior specified by the
governor in this document.

---

## 3. Data Sources

No new collections, no new tables. All inputs come from sources CORE already
maintains.

| Input | Source |
|-------|--------|
| Constitutional core | `.intent/` (cached) |
| Specifications | `.specs/` (via existing vector retrieval) |
| Role contract (system prompt) | `var/prompts/governor_ask/system.txt` |
| Input template (user prompt) | `var/prompts/governor_ask/user.txt` |
| Output contract (manifest) | `var/prompts/governor_ask/model.yaml` |
| Findings | `core.blackboard_entries` |
| Rules | Intent repository |
| Source files | `src/` (via direct read after vector-driven selection) |
| Consequence history | `core.consequence_log` |

---

## 4. Command Specification

```
core-admin ask "<question>" [--session <id>] [--plain]
core-admin ask --session <id> "<correction or follow-up>"
```

**Default mode:** Structured answer rendered with citations and grounding
labels for human reading.

**`--session` flag:** Continues an existing session. Correction within a
session re-triggers retrieval and reasoning with the correction weighted.
New questions within a session inherit accumulated context.

**`--plain` flag:** Plain text output without color codes; pipe and log
friendly.

**Side effects required:**
- Write session record and every turn to the consequence log
- Post contradiction findings to the Blackboard when retrieval surfaces them

**Side effects forbidden:**
- No code generation — `ask` reasons; it does not produce code
- No `.intent/` writes — interrogation is read-only with respect to law
- No proposal creation — proposals flow through existing surfaces

---

## 5. Answer Shape

The answer structure is primary; the prose rendering is derivative. Each
answer contains:

- **Claims** — individual statements, each labeled `grounded` or `inferred`
- **Provenance** — for grounded claims: rule ID, finding ID, specification
  path with section reference, or source file with line range
- **Unanswerable regions** — explicit statements naming what the question
  asks that cannot be answered from current state, and what would be
  required to answer it
- **Findings raised** — any contradictions surfaced during retrieval,
  posted to the Blackboard and referenced in the answer

The structure is validated by the PromptModel output contract (requirement
4 above). A response that does not conform is rejected before it reaches
the governor.

---

## 6. Session Semantics

Within a session:

- Previously retrieved context remains available for follow-ups
- Governor corrections are first-class input, not new unrelated questions
- Prior turns are composed into the next prompt, not discarded
- Each turn produces a consequence log entry referencing the session ID

Sessions close implicitly by governor non-use. Re-opening requires explicit
`--session <id>`; there is no automatic resumption.

---

## 7. Non-Requirements

The following are explicitly out of scope:

- Real-time streaming or TUI chat interface → batch request/response is
  sufficient at A3
- Natural-language policy amendment → interrogation is read-only with
  respect to `.intent/`
- Code generation → `ask` reasons; other workers produce
- Multi-governor or multi-tenant sessions → one governor per session
- Automatic pre-decision interrogation as a workflow phase → deferred to a
  later governance decision
- Replacement for `core-admin code audit`, `admin coverage`, or
  `runtime dashboard` → those remain structured-state surfaces; `ask` is
  the reasoning surface

---

## 8. Implementation Notes

**Constitutional alignment:**
This command is governed by the existing AI rule documents in
`.intent/rules/ai/` and enforced by the paired mappings in
`.intent/enforcement/mappings/ai/`:

- `ai.prompt.model_required`
- `ai.prompt.model_artifact_required`
- `ai.prompt.system_prompt_required`
- `ai.prompt.output_validation_required`
- `ai.prompt.artifact.required_fields`
- `ai.prompt.artifact.no_provider_leak`
- `ai.prompt.artifact.role_abstraction`
- `ai.cognitive_role.no_hardcoded_string`

No new rule document is required for this URS. The deliverables are: a
PromptModel artifact at `var/prompts/governor_ask/` containing `model.yaml`,
`system.txt`, and `user.txt`; a worker declaration at
`.intent/workers/governor_ask.yaml` conforming to the existing worker
schema; and a CLI command module.

**Known gap — cognitive role declaration:**
The `governor_ask` PromptModel requires a declared cognitive role
referenced by `model.yaml`. Whether an existing role in `core.cognitive_roles`
is suitable or a new role must be declared is an open question requiring
enumeration of current roles before implementation. `ai.prompt.artifact.role_abstraction`
forbids inventing role names; this must be settled in advance.

**Known gap — upstream traceability:**
This URS must trace to `.specs/northstar/CORE-USER-REQUIREMENTS.md` and
`.specs/northstar/core_northstar.md`. Neither has been reconciled with
this draft. Explicit upstream mapping is deferred to version 0.3 pending
that reconciliation.

**Known gap — citation verification scope:**
Version 0.2 requires verification that cited artifacts exist and contain
content consistent with the claim. The "consistent with" check is
implementable as textual or semantic match; stricter verification (logical
entailment between claim and cited content) is a later concern.

**Known gap — session persistence:**
Whether session state lives in memory, in the database, or on disk is an
open implementation question. The governor's requirement is only that
`--session <id>` continuations work; durability semantics are deferred.

---

## 9. Success Signal

The command is correct when the governor can:

1. Type a question in plain language
2. Receive an answer whose every claim can be traced to an artifact the
   governor can verify
3. See explicitly what the answer is grounded in, what is inferred, and
   what could not be answered
4. Correct the answer and get re-reasoning, not a fresh unrelated response
5. Find the session in the consequence log later and reconstruct the full
   chain of question, retrieval, answer, corrections, and findings raised

**Failure modes, stated explicitly:**

- If the governor must paste constitutional context into the question —
  the command has failed.
- If the answer contains uncited claims — the command has failed.
- If the answer improvises instead of saying *"I cannot answer this from
  current state"* — the command has failed.
- If correction is treated as a new unrelated question — the command has
  failed.
- If a session cannot be reconstructed from the consequence log — the
  command has failed.
