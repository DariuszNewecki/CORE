# Proof Index

CORE makes structural claims about AI-generated code: that `.intent/` is read through one gateway, that mutations cannot bypass the executor, that the API layer cannot reach the database directly, that every action is recorded, that a dangerous action cannot run without approval, and that every executed change is traceable end-to-end from finding to file change.

This page maps each claim to the mechanism that enforces it, the evidence a reviewer can observe, and a command that produces that evidence on a running instance. The page is intentionally short — six claims at v1, all verified against the codebase on the date of last update.

If a claim here cites a mechanism that no longer matches the code, the page is wrong and should be corrected before the code is.

---

## Claims

| # | Claim | Mechanism | Evidence | Command |
|---|---|---|---|---|
| 1 | `.intent/` is reached through a single gateway. | `IntentRepository` is the only class permitted to read `.intent/` files. The constraint is constitutional (CLAUDE.md rule 6) and preserved against decomposition by an explicit `governed_exclusions` entry that bars splitting the class. | The exclusion entry names IntentRepository as a constitutionally-required facade with a stated removal condition. | `grep -A 12 'intent_repository.py' .intent/enforcement/mappings/code/modularity.yaml` |
| 2 | `@atomic_action` functions cannot be called outside `ActionExecutor`. | The decorator at `src/shared/atomic_action.py` reads a governance token set by `ActionExecutor.execute()`. A direct call finds no token and raises `GovernanceBypassError` (defined at `src/shared/governance_token.py:21`). | A direct call from a Python REPL raises `GovernanceBypassError` with the message `Constitutional Violation: Action '<id>' was called directly. All actions MUST be routed through ActionExecutor.execute().` | See [Bypass smoke](#bypass-smoke) below. |
| 3 | The API layer holds no direct database imports. | Rule `architecture.api.no_direct_database_access` is mapped to the `ast_gate` engine at `.intent/enforcement/mappings/architecture/layer_separation.yaml`. The daemon runs it on a cadence and posts violations to the blackboard as `audit.violation::architecture.api.no_direct_database_access`. | A live database query returns the current open violation count. An empty result is PASS. | See [Audit-state query](#audit-state-query) below. |
| 4 | Every executed action is recorded in a database audit trail; a failed write-action record is surfaced, not silent. | `ActionExecutor._audit_log` writes a row to `core.action_results` for every executed action (`action_type`, `ok`, `file_path`, `agent_id`, `duration_ms`, and an `action_metadata` JSON with `session_id` and `impact`). The write is **best-effort** and runs after the action — it is **not** rolled back on failure (no file+DB transaction spans the mutation; #634). The table has no per-row failure mode (only `action_type`/`ok` are NOT NULL, both always supplied), so a failure means DB unavailability/serialization, not bad data. A `write=True` failure is logged at **ERROR** with an `AUDIT_GAP` marker — never swallowed; on the autonomous path the proposal's completion write shares the same DB and leaves the proposal visibly stuck, and `core.proposal_consequences` is a second (also best-effort) record. CLI-direct is the governor-operated residual. | Recent rows show real action IDs (`fix.duplicate_ids`, `sync.db`, …) with `agent_id = 'ActionExecutor'` and increasing `created_at` timestamps; an `AUDIT_GAP` log line is the failure signal. | See [Audit-trail query](#audit-trail-query) below. |
| 5 | A dangerous-impact action cannot auto-execute; it requires explicit governor approval. | Authorization of record is the approval layer, not an inline check. `.intent/enforcement/config/action_risk.yaml` classifies every action `safe \| moderate \| dangerous`; `Proposal.requires_approval` (`src/will/autonomy/proposal.py`) returns True for `moderate`/`high` risk — only `safe` auto-executes, and an unmapped action fails closed to `moderate`. `ActionExecutor._check_authorization` is a post-approval pass-through (not the gate); the audit → consequence loop is the post-hoc net. | The risk config lists actions classified `dangerous`/`moderate` (each behind approval), and `requires_approval` returns True for the `moderate`/`high` band. | `grep -E ': (dangerous\|moderate)$' .intent/enforcement/config/action_risk.yaml` |
| 6 | Every executed change is traceable end-to-end: finding → proposal → approval → execution → file change. | `core.proposal_consequences` records `pre_execution_sha` / `post_execution_sha` / `files_changed` per executed proposal; `core.autonomous_proposals` records each proposal's `goal` (the finding it resolves), `status`, `approved_by`, and `approval_authority`. Joined on `proposal_id`, they reconstruct the full causal chain — the same chain rendered in the README "Live Audit Trail." | A live join returns recent chains; each row carries the finding (`goal`), the authority that approved it (`risk_classification.safe_auto_approval` for risk-classified-safe auto-approval, or a human approver on the governor path), and the `pre → post` commit SHAs with the files changed. | See [Consequence-chain query](#consequence-chain-query) below. |

---

## Commands

The smokes assume a running CORE (`core-daemon` + `core-api`) and the project venv at `.venv/bin/python`. Each command is single-shot and reads only — none mutate state.

### Bypass smoke

```bash
.venv/bin/python -c "
import asyncio
from shared.atomic_action import atomic_action
from shared.action_types import ActionResult, ActionImpact
from shared.governance_token import GovernanceBypassError

@atomic_action(action_id='proof.demo', intent='proof', impact=ActionImpact.READ_ONLY, policies=[])
async def demo(**kwargs) -> ActionResult:
    return ActionResult(action_id='proof.demo', ok=True, data={}, impact=ActionImpact.READ_ONLY, duration_sec=0.0)

try:
    asyncio.run(demo())
    print('BYPASSED — proof broken')
except GovernanceBypassError as e:
    print('OK:', e)
"
```

Expected output:

```
OK: Constitutional Violation: Action 'proof.demo' was called directly. All actions MUST be routed through ActionExecutor.execute().
```

### Audit-state query

```bash
.venv/bin/python -c "
import asyncio
from shared.infrastructure.database.session_manager import get_session
from sqlalchemy import text

async def main():
    async with get_session() as s:
        rows = (await s.execute(text(\"\"\"
            SELECT subject, status, COUNT(*) AS n
            FROM blackboard_entries
            WHERE subject = 'audit.violation::architecture.api.no_direct_database_access'
            GROUP BY subject, status
        \"\"\"))).all()
        if not rows:
            print('PASS — no open violations of architecture.api.no_direct_database_access')
        else:
            for r in rows: print(r)
asyncio.run(main())
"
```

A `PASS` line means the daemon's most recent audit cycle found no API-layer file with a forbidden database import. A non-empty result names each violation status (open / abandoned / resolved) with a count.

### Audit-trail query

```bash
.venv/bin/python -c "
import asyncio
from shared.infrastructure.database.session_manager import get_session
from sqlalchemy import text

async def main():
    async with get_session() as s:
        rows = (await s.execute(text(
            'SELECT action_type, ok, agent_id, created_at FROM core.action_results ORDER BY id DESC LIMIT 5'
        ))).all()
        for r in rows: print(r)
asyncio.run(main())
"
```

Each row is one executed atomic action. Reviewer should observe: `agent_id` is always `ActionExecutor` (no other writer is permitted), `action_type` matches a real registered action ID, and timestamps increase monotonically.

### Consequence-chain query

```bash
.venv/bin/python -c "
import asyncio
from shared.infrastructure.database.session_manager import get_session
from sqlalchemy import text

async def main():
    async with get_session() as s:
        rows = (await s.execute(text('''
            SELECT ap.goal, ap.status, ap.approved_by, ap.approval_authority,
                   left(pc.pre_execution_sha, 8)  AS pre_sha,
                   left(pc.post_execution_sha, 8) AS post_sha,
                   (SELECT string_agg(f->>'path', ', ')
                      FROM jsonb_array_elements(pc.files_changed) f) AS files_changed,
                   pc.recorded_at
            FROM core.proposal_consequences pc
            JOIN core.autonomous_proposals ap ON ap.proposal_id = pc.proposal_id
            ORDER BY pc.recorded_at DESC
            LIMIT 5
        '''))).mappings().all()
        for r in rows: print(dict(r))
asyncio.run(main())
"
```

Each row is one complete consequence chain. `goal` is the finding that triggered it (e.g. `Autonomous remediation: fix.format (1 violation(s) — rules: style.formatter_required ...)`); `approved_by` / `approval_authority` is the authority that authorized execution — `risk_classification.safe_auto_approval` on the risk-classified-safe autonomous path, or `principal.governor` on the human-approval path; `pre_sha → post_sha` with `files_changed` is the executed mutation. This is the query behind the README "Live Audit Trail" — the causal chain (Finding → Proposal → Approval → Execution → File change) read end-to-end from one join.

---

## Boundaries

The claims above state what CORE enforces. This section states where a named mechanism's coverage **deliberately** ends, so a reviewer does not read an out-of-scope path as a gap.

**Worktree execution sandbox (ADR-106 / ADR-071 D2.2).** Write actions execute inside a hermetic git worktree — mutations land in the sandbox and are copy-propagated back only on success, bounded to the declared production set — **only when the caller supplies `pre_execution_sha`**. The autonomous/daemon path supplies it (`src/will/autonomy/proposal_executor.py`, `proposal_execution_pipeline.py`); a **direct CLI invocation leaves it `None` and executes against the real working tree by design**. The boundary is intentional: CLI is a governor-operated surface — the operator authored the change and runs under the D2.1 stop/start protocol — so it is out of sandbox scope, not an oversight. This mirrors the authorization boundary in claim 5: a CLI-direct dangerous write is the same named residual, covered by governor operation plus the audit → consequence loop rather than by the inline mechanism.

Verify the gate: `grep -n "pre_execution_sha is None" src/body/atomic/sandbox_lifecycle.py` shows the sandbox is skipped when no sha is supplied; `grep -rn "pre_execution_sha=" src/will/autonomy/` shows the autonomous callers that supply it. No CLI path does.

---

## Scope

V1 covers six claims chosen for what they prove together: a single read gateway (1), no executor bypass (2), no layer bypass at the API surface (3), no untracked mutation (4), no auto-execution of a dangerous action without approval (5), and end-to-end causal traceability from finding to file change (6). Other claims worth adding — autonomous test-loop honesty, blackboard-only worker communication, atomic-action contract enforcement — are deferred until the cited mechanisms stabilize.

If you find a row whose command no longer produces the cited evidence, the disagreement is the bug, not the test.

---

*Last verified: 2026-06-14 against `main`.*
