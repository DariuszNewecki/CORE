# Proof Index

CORE makes structural claims about AI-generated code: that `.intent/` is read through one gateway, that mutations cannot bypass the executor, that the API layer cannot reach the database directly, that every action is recorded.

This page maps each claim to the mechanism that enforces it, the evidence a reviewer can observe, and a command that produces that evidence on a running instance. The page is intentionally short — four claims at v1, all verified against the codebase on the date of last update.

If a claim here cites a mechanism that no longer matches the code, the page is wrong and should be corrected before the code is.

---

## Claims

| # | Claim | Mechanism | Evidence | Command |
|---|---|---|---|---|
| 1 | `.intent/` is reached through a single gateway. | `IntentRepository` is the only class permitted to read `.intent/` files. The constraint is constitutional (CLAUDE.md rule 6) and preserved against decomposition by an explicit `governed_exclusions` entry that bars splitting the class. | The exclusion entry names IntentRepository as a constitutionally-required facade with a stated removal condition. | `grep -A 12 'intent_repository.py' .intent/enforcement/mappings/code/modularity.yaml` |
| 2 | `@atomic_action` functions cannot be called outside `ActionExecutor`. | The decorator at `src/shared/atomic_action.py` reads a governance token set by `ActionExecutor.execute()`. A direct call finds no token and raises `GovernanceBypassError` (defined at `src/shared/governance_token.py:21`). | A direct call from a Python REPL raises `GovernanceBypassError` with the message `Constitutional Violation: Action '<id>' was called directly. All actions MUST be routed through ActionExecutor.execute().` | See [Bypass smoke](#bypass-smoke) below. |
| 3 | The API layer holds no direct database imports. | Rule `architecture.api.no_direct_database_access` is mapped to the `ast_gate` engine at `.intent/enforcement/mappings/architecture/layer_separation.yaml`. The daemon runs it on a cadence and posts violations to the blackboard as `audit.violation::architecture.api.no_direct_database_access`. | A live database query returns the current open violation count. An empty result is PASS. | See [Audit-state query](#audit-state-query) below. |
| 4 | Every action mutation is recorded in a database audit trail. | `ActionExecutor._audit_log` (`src/body/atomic/executor.py:369`) writes a row to `core.action_results` for every executed action, with `action_type`, `ok`, `file_path`, `agent_id`, `duration_ms`, and a JSON `action_metadata` payload that includes `session_id` and `impact`. The write is non-blocking — audit failure is logged, not raised. | Recent rows show real action IDs (`fix.duplicate_ids`, `sync.db`, …) with `agent_id = 'ActionExecutor'` and increasing `created_at` timestamps. | See [Audit-trail query](#audit-trail-query) below. |

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

---

## Scope

V1 covers four claims chosen for what they prove together: a single read gateway (1), no executor bypass (2), no layer bypass at the API surface (3), no untracked mutation (4). Other claims worth adding — autonomous test-loop honesty, blackboard-only worker communication, atomic-action contract enforcement — are deferred until the cited mechanisms stabilize.

If you find a row whose command no longer produces the cited evidence, the disagreement is the bug, not the test.

---

*Last verified: 2026-06-06 against `main`.*
