<!-- path: .intent/papers/CORE-ViolationExecutor.md -->

# CORE — ViolationExecutor

**Status:** Canonical
**Authority:** Policy
**Scope:** AtomicAction discovery for unmapped rules

---

## 1. Purpose

This paper defines the ViolationExecutor — the acting Worker that
handles violations for rules that have no RemediationMap entry by
invoking an LLM to reason about a fix, and surfacing the result as
an AtomicAction candidate for human review.

---

## 2. Definition

The ViolationExecutor is the discovery path of the remediation system.

It operates exclusively on unmapped rules — rules for which no AtomicAction
has been declared in the RemediationMap. It does not compete with the
RemediatorWorker. The RemediationMap is the partition key: mapped rules
belong to RemediatorWorker; unmapped rules belong to ViolationExecutor.

The primary output of ViolationExecutor is not an applied fix. It is a
**remediation pattern** — evidence that a particular LLM-reasoned fix
worked for a particular rule, surfaced as a candidate for codification
into an AtomicAction.

When an AtomicAction is codified and added to the RemediationMap, the
rule graduates to the constitutional path. ViolationExecutor never
touches that rule again. Reducing ViolationExecutor's workload to zero
means CORE has fully codified its remediation knowledge — not that
ViolationExecutor has been retired.

---

## 3. Relationship to RemediatorWorker

The ViolationExecutor and RemediatorWorker are not peers. They operate
on disjoint finding sets and serve different purposes.

| | RemediatorWorker | ViolationExecutor |
|---|---|---|
| **Handles** | Mapped rules | Unmapped rules |
| **Mechanism** | Deterministic routing | LLM reasoning |
| **Primary output** | Proposal → AtomicAction | AtomicAction candidate |
| **Target state** | Handles all findings | Handles zero findings |

RemediatorWorker has priority. It runs first and claims all findings
whose rules are mapped. ViolationExecutor claims only what remains —
findings whose rules have no active RemediationMap entry.

The RemediationMap gate (Step 4) enforces this partition at runtime as
a safety check. When the gate fires — meaning a race condition caused
ViolationExecutor to claim a finding whose rule was mapped after the
claim — ViolationExecutor **releases** the claim back to `open` by
calling `release_claimed_entries`. It does not resolve the finding.
RemediatorWorker will reclaim it on the next cycle.

---

## 4. Graduation Path

A rule graduates from ViolationExecutor's domain to RemediatorWorker's
domain through the following steps:

1. ViolationExecutor handles the violation and surfaces a candidate fix.
2. The OptimizerWorker (once implemented) observes repeated successful
   patterns for the same rule and proposes an AtomicAction. Until the
   OptimizerWorker exists, the human architect performs this step
   directly by observing ViolationExecutor output on the Blackboard.
   See `CORE-OptimizerWorker.md`.
3. The human architect reviews and approves the AtomicAction.
4. The AtomicAction is registered and added to the RemediationMap.
5. The rule is now mapped. RemediatorWorker owns it from that point forward.

This graduation process is the mechanism by which CORE's remediation
knowledge grows. ViolationExecutor is the instrument of discovery.
OptimizerWorker is the instrument of codification — when it exists.

---

## 5. Technical Flow

start → register → run → heartbeat → claim findings
→ group by file → plan file → check RemediationMap gate → invoke LLM
→ pack Crate → align staged file → run Canary
→ apply or post dry-run → surface candidate → post report → end

**Step 1 — Claim findings**
Atomically claims open findings whose rule has no active RemediationMap
entry. Up to 50 per run.

**Step 2 — Group by file**
Findings are grouped by `file_path`. One LLM invocation per file
covers all violations in that file.

**Step 3 — Plan file (Runtime phase)**
For each file:
- Read the source file from disk.
- Record the git baseline SHA.
- Build an architectural context package via `RemediationInterpretationService`.
  This produces a role detection, confidence score, and candidate strategies.
- If confidence < 0.55 in write mode: mark findings `indeterminate` and halt.

**Step 4 — Check RemediationMap gate**
Before invoking the LLM, re-check whether the finding's rule has an active
mapping in the RemediationMap (race condition guard). If it does: call
`release_claimed_entries` to reset findings to `open` status and return
False. ViolationExecutor does not resolve findings that belong to
RemediatorWorker. RemediatorWorker will claim them on the next cycle.

**Step 5 — Invoke LLM (Execution phase)**
The LLM is invoked via `PromptModel.load("violation_remediator")` with:
- The source file content
- The violations summary
- The architectural context (advisory, not authority)
- The rule ID

The LLM returns a JSON object: `{code, rationale, violations_addressed}`.
The `code` field is extracted and validated as syntactically valid Python.

If the LLM returns empty, invalid JSON, or invalid Python: findings are
marked `abandoned`.

**Step 6 — Pack Crate**
The proposed fix is packed into a Crate via `crate.create`.

**Step 7 — Align staged file**
After packing, `_align_staged_file()` runs `black` and
`ruff --select I --fix` on the staged file inside the Crate. This is
best-effort — failure does not block the Canary.

**Step 8 — Run Canary**
The Canary validates the Crate in a sandbox.

**Step 9 — Apply or post dry-run**

In dry-run mode (`write=False`):
- The Crate is not applied.
- The proposed fix is posted to the Blackboard as `dry_run_complete`.
- Findings are marked `dry_run_complete` with `dry_run_scope: fix_generated`.

In write mode (`write=True`):
- A rollback archive is written to `var/mind/rollbacks/`.
- The Crate is applied.
- A git commit is made.
- Findings are marked `resolved`.

**Step 10 — Surface candidate**
Regardless of write mode, the rationale and fix pattern are posted to
the Blackboard as an AtomicAction candidate for the rule. This is the
primary discovery output. The OptimizerWorker will consume these
candidates once implemented. Until then, the human architect monitors
them directly. See `CORE-OptimizerWorker.md`.

---

## 6. Implementation Status

**Not yet implemented.**

The ViolationExecutor has no corresponding worker file in `src/will/workers/`.
This paper defines the intended design. The absence of implementation is a
known capability gap: CORE currently has no autonomous path for unmapped rules.

The implementation gap means:
- Unmapped rules produce findings that no worker handles.
- No AtomicAction discovery is occurring.
- The graduation path to RemediatorWorker is blocked.

---

## 7. Non-Goals

This paper does not define:
- the PromptModel format or template
- the LLM provider
- the architectural context service
- the OptimizerWorker's codification logic — see `CORE-OptimizerWorker.md`
- the human review interface for AtomicAction candidates
