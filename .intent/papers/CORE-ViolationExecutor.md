<!-- path: .intent/papers/CORE-ViolationExecutor.md -->

# CORE — ViolationExecutor

**Status:** Canonical
**Authority:** Policy
**Scope:** LLM-direct remediation fallback

---

## 1. Purpose

This paper defines the ViolationExecutor — the acting Worker that
handles rules without a RemediationMap entry using direct LLM invocation.

---

## 2. Definition

The ViolationExecutor is the legacy remediation path. It handles
violations that the RemediatorWorker cannot route to an AtomicAction.

It is not the target state. Every rule it handles is a rule that has
not yet been given a proper AtomicAction. The goal is to reduce its
workload to zero.

---

## 3. Technical Flow

start → register → run → heartbeat → claim findings
→ group by file → plan file → check RemediationMap gate → invoke LLM
→ pack Crate → align staged file → run Canary
→ apply or post dry-run → post report → end

**Step 1 — Claim findings**
Atomically claims open findings for its `target_rule` from the Blackboard.
Up to 50 per run.

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
Before invoking the LLM, check whether the finding's rule has an active
mapping in the RemediationMap. If it does: mark findings
`deferred_to_proposal` and return False. The Worker defers to the
constitutional path.

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
- Findings are marked `dry_run_complete`.

In write mode (`write=True`):
- A rollback archive is written to `var/mind/rollbacks/`.
- The Crate is applied.
- A git commit is made.
- Findings are marked `resolved`.

---

## 4. Non-Goals

This paper does not define:
- the PromptModel format or template
- the LLM provider
- the architectural context service
