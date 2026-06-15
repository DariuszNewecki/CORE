---
kind: adr
id: ADR-109
title: ADR-109 — Assisted Remediation Lane
status: accepted
---

<!-- path: .specs/decisions/ADR-109-assisted-remediation-lane.md -->

# ADR-109 — Assisted Remediation Lane

**Status:** Accepted
**Date:** 2026-06-15
**Authors:** Darek (Dariusz Newecki)
**Relates to:** ADR-035 (One Finding, One Proposal), ADR-029 (non-automatable
rule mapping), ADR-038 (circuit breaker → DELEGATE), ADR-045 (revival /
quarantine), ADR-010 (Finding/Proposal contract + §7a revival), ADR-101
(commit set = sandbox production; authorship), CORE-Finding §7b (indeterminate
exit), the A3 plan ("delegate correctly when human judgment is required").

---

## Context

CORE's autonomous remediation loop is deliberately bounded: one proposal per
`(action, file)` (ADR-035), single-file atomic actions, no AI decisions in
Body, and explicit delegation of non-automatable rules to the human
(ADR-029). When a rule is mapped `DELEGATE` (confidence < 0.80, e.g.
`modularity.class_too_large`: "class-level refactors are architectural
judgment — non-automatable") or a proposal trips the circuit breaker
(ADR-038), the finding is transitioned to `status='indeterminate'`,
`resolution_mechanism='human'` (`mark_indeterminate`) and surfaced in the
Governor Inbox (`GOVERNOR_INBOX_SQL`).

**The gap: a delegated finding has no path to be *worked*.** The only governor
exits today are `resolve_indeterminate_entry` (close with a reason) or
abandon. There is no mechanism by which the delegated work actually gets
*done* — so "delegate to human" is, in practice, "park indefinitely." The A3
plan names "delegate correctly when human judgment is required" as a
first-class responsibility, but the safety valve it assumes was built only as
a parking lot, never as a working lane.

### Observed evidence (2026-06-15)

A review of the live Governor Inbox found **110 items; ~90% stale.** Of 7
`approval_required` proposals, **0 were actionable** (all targeted deleted or
already-fixed files). Of 103 delegates, **30 targeted deleted files and 54
were already resolved** — only **11 were confirmed-real**, plus 5 blocked
behind a dispatch bug and 3 graph-integrity findings. The inbox had been
accumulating for up to a month. The backlog is not signal; it is the absence
of a lane to drain it.

### Why the autonomous loop cannot drain it (and should not)

The confirmed-real findings are exactly the categories governance reserves for
human judgment: orphan-file deletion (destructive, and demonstrably
false-positive-prone — `llm_judge.py` was flagged orphan while still
imported), CLI verb renames (breaking public surface), AST-duplication
hoists, and architectural reroutes. Most require **coherent cross-file**
changes (hoist a method to `BaseEngine` *and* remove it from N subclasses),
which the single-file proposal/action model structurally cannot express. This
is correct: making the *unattended* loop perform high-blast-radius,
judgment-heavy, cross-file changes would fight the safety posture that makes
it safe to run unattended.

### What already exists (the lane is mostly assembly, not new capability)

- **Multi-file context assembly** — `ContextService.build_for_task` already
  accepts a `target_files` list (`target_file` + `scope.include`) and gathers
  AST/DB/vector evidence across them.
- **Multi-file execution** — `FlowExecutor` runs steps in one sandbox; the
  production set is the union of touched files. `ProposalScope.files` is a
  blast-bounded list.
- **Sandbox / validate / approve / commit** — governed and present (ADR-071,
  ADR-101).
- **Lifecycle states** — `deferred_to_proposal`, revival on rejection
  (ADR-010 §7a, ADR-045) already exist.

What is missing is a **router**, a **human-gated multi-file proposal
allowance**, and an **agent entry point**.

---

## Decision

Establish the **Assisted Remediation Lane**: a governed workflow by which a
delegated finding is worked by an **external interactive agent** (Claude Code)
with full multi-file context, and submitted back as a single **human-gated
multi-file proposal** that the governor reviews and CORE executes through the
existing sandbox/validate/commit pipeline.

**D1 — A delegated finding gets a working path, not only a close/abandon
exit.** This operationalizes the A3 "delegate correctly" responsibility. The
lane consumes findings where `status='indeterminate'` AND
`resolution_mechanism='human'`.

**D2 — The interactive agent is external (Claude Code).** CORE does not build
an in-process LLM orchestrator. CORE *exposes* the finding plus assembled
multi-file context, and *ingests* an agent-produced, governor-approved change.
The agent reasons and produces the diff using its own repository tooling; CORE
owns the governance gate, validation, and commit. (An in-CORE interactive
worker is explicitly deferred — it is a larger build and inherits the
single-file coder limits this lane routes around.)

**D3 — Human-gated multi-file proposals (extends ADR-035).** In the assisted
lane *only*, a proposal MAY span N interdependent files and is approved as one
unit. ADR-035's per-file scoping exists for *approval granularity under
autonomous trust* — the governor could not be asked to approve a bundle the
*daemon* assembled. That concern is dissolved when a human reviews the actual
multi-file diff: the unit of approval becomes the coherent change the human
inspected. Therefore `approval_required = true` is **mandatory** for every
assisted-lane multi-file proposal; the human gate is the precondition that
licenses the multi-file exception. ADR-035 remains unchanged for the
autonomous loop.

**D4 — Reuse the existing lifecycle; add no new status.** A finding's journey:
`indeterminate+human` (delegated, in inbox) → agent claims and submits → the
finding transitions to `deferred_to_proposal` linked to the assisted proposal
(out of the inbox, tracked) → governor reviews the diff → on approve, CORE
validates and commits, finding → `resolved`; on reject, the finding revives to
`indeterminate+human` (ADR-010 §7a / ADR-045). The autonomous remediator's
claim query (`status='open'`) never sees these, so there is no double-work.

**D5 — Commit authorship is joint (ADR-101 D1).** The agent authored the diff
bytes; the governor authorized the merge. Assisted-lane commits carry a
`Co-Authored-By` trailer and derive their commit set from the sandbox
production (ADR-101 D2), not from `scope.files`.

---

## Mechanism (implementation guidance — not frozen)

A small `core-admin lane` command group is the external-agent contract:

1. **`lane next` / `lane list`** — return the top (or all) delegated findings
   with a **context bundle**: the finding payload, the assembled multi-file
   context (`ContextService.build_for_task` over the finding's file plus
   derived related files — callers, base classes, siblings), the
   remediation-map `description` guidance, and the relevant rule text. This is
   the agent's "pull work" surface.
2. **`lane claim <finding>`** — mark the finding as being worked (records
   agent identity + timestamp) so it is visibly in-progress, not parked.
3. **`lane propose <finding>`** — ingest an agent-produced **sandbox
   multi-file diff** as a governed proposal (`status=draft`,
   `approval_required=true`, `scope.files=[…the touched set…]`, linked to the
   finding; finding → `deferred_to_proposal`).
4. **Validation gate** — before the proposal is approvable, CORE re-validates
   the diff *in sandbox*: the audit is clean on the touched files (the offending
   rule no longer fires), `ruff` passes, and the relevant tests run. A diff
   that does not clear validation cannot be approved.
5. **Approval + execute** — the existing `core-admin proposals approve` /
   `execute` path applies the sandbox production and commits it atomically as
   one consequence, attributed jointly.

The one genuinely new execution primitive is **diff ingestion**: accepting an
agent-produced sandbox diff as a proposal's production set (rather than
computing it from `actions`). Everything else reuses existing infrastructure.

---

## Consequences

**Positive**
- Delegated findings stop accumulating: the inbox becomes a true work queue
  with a drain, not a parking lot.
- Coherent cross-file changes (the category the autonomous loop cannot do
  safely) become possible *under human review*, without loosening autonomous
  bounds.
- Minimal new code: a CLI surface, a multi-file-proposal allowance, and a
  diff-ingest primitive over existing context/execution/commit machinery.
- The governor reviews a real, validated, multi-file diff — stronger evidence
  than approving an action description.

**Negative**
- Multi-file proposals have larger blast radius; the mandatory human gate plus
  in-sandbox validation (D3, mechanism §4) are the mitigations. The blast
  bound on `scope.files` still applies.
- Diff ingestion is a new trust surface: CORE must validate an externally
  produced diff, not just its own action output. Validation (audit + ruff +
  tests in sandbox) and ADR-101 authorship rules bound it.

**Neutral**
- The external-agent choice (D2) means the lane's reasoning quality tracks
  whatever agent the governor drives; CORE governs the *gate*, not the
  reasoning. An in-CORE orchestrator can be added later without changing the
  finding lifecycle (D4).

---

## Deferred scope (file as issues before implementation)

- The `lane` CLI command group (`next`/`list`/`claim`/`propose`).
- The context-bundle exporter (finding + multi-file `ContextService` context +
  guidance), and the related-file derivation.
- The diff-ingest primitive + the multi-file in-sandbox validation gate.
- The ADR-035 D3 amendment note (assisted-lane multi-file exception).

---

## References

- ADR-035 — One Finding, One Proposal (the per-file scoping this lane extends
  under human gate)
- ADR-029 — explicit non-automatable rule mapping (`DELEGATE`/`PENDING`)
- ADR-038 — circuit breaker → DELEGATE (a second delegation source)
- ADR-045 / ADR-010 §7a — revival on rejection (reused for D4)
- ADR-101 — commit set = sandbox production; joint authorship (D5)
- CORE-Finding §7b — `indeterminate` exit requires human action
- `src/will/workers/violation_remediator.py` — where `DELEGATE` is routed
- `src/body/services/blackboard_service/blackboard_service.py` —
  `mark_indeterminate` / `resolve_indeterminate_entry` (the current dead-end)
- `src/shared/infrastructure/context/service.py` — `build_for_task`
  (multi-file context, reused)
- `GOVERNOR_INBOX_SQL` (`health_log_service.py`) — the inbox predicate
- Observed inbox state, 2026-06-15: 110 items, ~90% stale, 11 confirmed-real
