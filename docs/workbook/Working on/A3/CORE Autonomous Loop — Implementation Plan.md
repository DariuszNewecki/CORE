# CORE Autonomous Loop — Implementation Plan
*March 2026 · Internal reference*

---

## Guiding Principle

Every component described here either already exists in the architecture or is
a direct constitutional obligation not yet implemented. Nothing here is new
invention — it is closing the gap between what the constitution declares and
what currently runs.

---

## Architectural Decisions (Locked)

**Awakening trigger:** `asyncio` periodic loop inside a long-running process,
started by Sanctuary. Workers are independents — each owns and manages its own
cadence, declared in `.intent/`. No central scheduler. No worker knows other
workers exist.

**Scheduling model:** Each worker reads its own `schedule.max_interval`
(seconds) from its `.intent/` declaration on startup and drives its own loop.
The Orchestrator does not schedule — it only monitors.

**Liveness formula:**
```
violation when: now() - last_heartbeat > max_interval + glide_off
where:          glide_off = max_interval * 0.10  (default, per-worker override allowed)
```
`glide_off` absorbs timing jitter without masking real silence. Both
`max_interval` and `glide_off` are declared in `.intent/` — not hardcoded.
Future: CORE evaluates heartbeat history from `system_health_log` and proposes
adjusted `glide_off` values per worker as a constitutional proposal.

**Orchestrator authority:** Monitoring worker liveness — including marking
a silent worker `abandoned` — is within the Orchestrator's declared mandate.
No human approval required for liveness enforcement.

**Strategic memory:** Dedicated `core.system_health_log` table. Append-only.
Every Observer run writes one row. The Blackboard is for active coordination —
the health log is for accumulated self-knowledge. Separate concerns, separate tables.

---

## Worker YAML Schema — Schedule Extension

The existing `.intent/META/worker.schema.json` gains one new optional block
under `mandate`. Existing workers without `schedule` declared are not affected.

```yaml
# Addition to mandate block — example: observer_worker.yaml
mandate:
  responsibility: >
    Observe system state and post a structured situation report to the Blackboard.
  phase: audit
  approval_required: false
  schedule:
    max_interval: 300        # seconds — constitutional commitment
    glide_off: 30            # seconds — override default (10% of max_interval)
```

`glide_off` is optional — defaults to `max_interval * 0.10` if absent.
`max_interval` is required for any worker that self-schedules.
Workers without `schedule` declared are invoked externally (existing behaviour,
e.g. DocWorker called by CLI or Blackboard event).

---

## Current State vs Target State

| Concern | Now | Target |
|---|---|---|
| Audit | Human-triggered CLI snapshot | Permanent domain auditors, always running |
| Scheduling | Human invokes workers | Workers self-schedule via `asyncio` loop |
| Blackboard | Workers post when invoked | Auditors seed continuously |
| Orchestrator | Human (you) | ShopManager liveness watchdog only |
| Reporter | `core-admin check audit` | Blackboard-read-only Reporter |
| Strategic memory | In human's head | `core.system_health_log` table |

---

## Phase 1 — Background Observer

**What:** A `sensing` worker that self-schedules via `asyncio`, reads system
state, and posts a structured situation report to the Blackboard.
No LLM required. Pure deterministic perception.

**Reads:**
- `core.blackboard_entries` — open/stale entries, entry age, ownership gaps
- `core.worker_registry` — last heartbeat per worker, status
- `core.audit_findings` — unresolved violations by domain
- `core.symbols` — orphaned, untagged, undocumented counts

**Writes:**
- One `report` entry to Blackboard: subject `observer.situation_report`
- One row to `core.system_health_log` (append-only, never updated)

**`core.system_health_log` schema (migration required before Phase 1):**
```sql
CREATE TABLE core.system_health_log (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    observed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    open_findings    INTEGER NOT NULL,
    stale_entries    INTEGER NOT NULL,
    silent_workers   INTEGER NOT NULL,
    orphaned_symbols INTEGER NOT NULL,
    payload          JSONB NOT NULL DEFAULT '{}'
);
```

**Declaration:** `.intent/workers/observer_worker.yaml`
class: `sensing`, phase: `audit`, `schedule.max_interval: 300`

**Effort:** Low. No new infrastructure. Reuses `Worker` base + `get_session`.

---

## Phase 2 — Permanent Domain Auditors

**What:** Replace the single ad-hoc `audit` CLI with always-on `governance`
workers, each owning one constitutional domain, each self-scheduling.

**Initial set:**

| Worker | Domain | Source of logic | `max_interval` |
|---|---|---|---|
| `ConstitutionAuditor` | Rule violations, layer boundaries | Port from `check.audit` | 600s |
| `SymbolAuditor` | Orphaned, untagged, undocumented symbols | Port from `capability-tagger` | 1800s |
| `BlackboardAuditor` | Stale entries, SLA breaches, unclaimed findings | New | 120s |
| `WorkerAuditor` | Silent workers, missed heartbeats | Port from ShopManager logic | 120s |

**Each auditor:**
- Self-schedules via `asyncio` loop using declared `max_interval`
- Posts findings to Blackboard — never acts on them
- Uses existing `Worker` deduplication to avoid re-posting known violations
- No LLM — deterministic scan only

**Key shift:** `core-admin check audit` becomes a read command, not a scan.

**Effort:** Medium. Logic exists in CLI commands — needs extraction into
Worker classes with `.intent/` declarations.

---

## Phase 3 — Orchestrator Heartbeat (ShopManager)

**What:** The `ShopManager` as a continuous `asyncio` loop. Liveness watchdog
only — does not schedule, does not understand finding content.

**Reconciliation protocol:**
```
every N seconds (declared in .intent/):

  for each worker in worker_registry where status = 'active':
    threshold = max_interval + glide_off   ← read from worker's .intent/ declaration
    if now() - last_heartbeat > threshold:
      mark worker status = 'abandoned'
      post finding: worker.silent (payload carries worker UUID and breach duration)

  for each open blackboard entry:
    if now() - created_at > entry_sla:    ← sla declared in .intent/enforcement/
      post finding: blackboard.entry_stale

  if no violations found:
    post report: system.healthy
    write row to system_health_log
```

**Reads worker schedule from:** `.intent/workers/<name>.yaml` →
`mandate.schedule.max_interval` + `mandate.schedule.glide_off`

**Effort:** Medium. Needs continuous loop + SLA declarations in `.intent/`.

---

## Phase 4 — Validator Chain

**What:** Deterministic gate between `proposal` creation and `execution`.
No LLM. Rejects non-compliant Specialist output before it reaches live code.

**Minimum viable validators:**

| Validator | Rule | Method |
|---|---|---|
| `PathCommentValidator` | File starts with `# path/to/file.py` | String check |
| `LayerBoundaryValidator` | No Body→Will imports at runtime | AST |
| `ConstitutionalHeaderValidator` | Worker files declare `LAYER:` in header | String check |
| `UUIDValidator` | Blackboard entry carries valid worker UUID | DB check |

A failed validator posts `validation.failed` to Blackboard — visible to
Orchestrator as a stale unclaimed entry → triggers accountability check.

**Effort:** Low per validator. AST gate infrastructure already exists.

---

## Phase 5 — Reporter

**What:** Replaces `core-admin check audit`. Reads pre-existing state only.
No scan triggered.

**Reads:**
- Open findings by domain and age
- Worker liveness from `worker_registry`
- Latest N rows from `core.system_health_log` → shows trend, not just snapshot

**CLI:** `core-admin report status`

**The health log makes this powerful:** not just current state but direction —
is the system getting healthier or drifting?

**Effort:** Low. DB reads + formatting.

---

## Sequencing

```
DB migration (system_health_log)   ← prerequisite for Phase 1
Phase 1 (Observer)                 ← lowest risk, establishes health_log
Phase 2 (Auditors)                 ← port existing logic, high value
Phase 5 (Reporter)                 ← unblocks visibility, uses health_log trend
Phase 3 (Orchestrator)             ← needs Phase 1+2 data to be meaningful
Phase 4 (Validators)               ← parallel to Phase 3, one validator at a time
```

Phases 1 + 2 + 5 = **minimum viable autonomous loop.**
Phases 3 + 4 = **closed loop.**

---

## LLM Routing

| Task | Tier | Model |
|---|---|---|
| Observer scan, health log writes | None | No LLM |
| Auditor domain scans | None | No LLM |
| Orchestrator liveness check | None | No LLM |
| Validation gate | None | No LLM |
| Finding classification / tagging | Small local | Ollama / Qwen |
| First-pass fix proposals | Small local | Ollama / Qwen |
| `glide_off` tuning proposals | Small local | Ollama / Qwen |
| Architectural / constitutional decisions | Strategic | Large model |

The autonomous heartbeat costs zero inference.

---

## What Does NOT Change

- `Worker` base class — already correct
- Blackboard schema — already correct
- `.intent/` declaration format — extended only (new `schedule` block)
- Phase system — already correct
- `PromptModel` for all LLM calls — constitutional law, unchanged
- `get_session` in `will/workers/` — constitutionally permitted via existing exclusion
