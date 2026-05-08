<!-- path: .specs/papers/CORE-AutonomousProposalWorker.md -->

# CORE — Autonomous Proposal Worker

**Status:** Canonical
**Authority:** Policy
**Scope:** LLM-driven proposal generation from audit findings (superseded)

---

## 1. Purpose

This paper defines the `AutonomousProposalWorker` — the acting Worker that
used LLM reasoning to generate remediation proposals directly from audit
findings.

---

## 2. Status: Superseded

`AutonomousProposalWorker` is paused and superseded by the
`ViolationRemediatorWorker` + `ProposalConsumerWorker` pipeline.

The original design had this worker read recent ERROR findings from
`core.audit_findings`, invoke `PromptModel` reasoning, and create Proposal
objects in `ProposalRepository`. The approach worked but carried LLM overhead
and reasoning risk on every proposal creation cycle.

The current pipeline achieves the same outcome deterministically: `ViolationRemediatorWorker`
looks up the remediating action from `auto_remediation.yaml` mappings — no LLM
required. `ProposalConsumerWorker` executes approved proposals. The mapping is
explicit, auditable, and does not vary between runs.

`AutonomousProposalWorker` is retained in the worker registry as a paused
declaration. It is not activated in the daemon. Its YAML declaration is the
constitutional record of why the approach was tried and what replaced it.

---

## 3. Constitutional Identity (Historical)

| Field | Value |
|---|---|
| Declaration | `.intent/workers/proposal_worker.yaml` |
| Class | `acting` |
| Phase | `execution` |
| LLM | `llm.remote_coder` |
| Approval required | false |
| Schedule | max_interval 600 s |

---

## 4. Why It Was Superseded

The deterministic mapping approach (ADR-014, `auto_remediation.yaml`) is
preferable to LLM reasoning for proposal generation because:

- Mapping outcomes are reproducible. The same finding produces the same
  proposal action every time.
- Mapping failures are detectable. A missing mapping entry is a visible gap,
  not a silent reasoning error.
- Mapping has no inference cost. No LLM call is made until the execution stage.
- Mapping is governable. The `auto_remediation.yaml` file is a constitutional
  artifact subject to the same rules as any other governance document.

LLM-driven proposal generation remains the correct approach for novel findings
with no mapping entry — this is the `ViolationExecutorWorker` path.

---

## 5. Non-Goals

This paper does not define:
- the current proposal generation mechanism (see `CORE-RemediationMap.md`)
- `ViolationRemediatorWorker` (see `CORE-RemediatorWorker.md`)
- `ViolationExecutorWorker` (see `CORE-ViolationExecutor.md`)

---

## 6. Amendment Discipline

This paper may be amended only by explicit constitutional replacement, in
accordance with the CORE amendment mechanism.
