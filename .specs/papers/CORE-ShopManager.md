<!-- path: .intent/papers/CORE-ShopManager.md -->

# CORE — ShopManager

**Status:** Canonical
**Authority:** Policy
**Scope:** Worker supervision
**Implementation:** Partial — Worker health (active), Blackboard integrity (active), Proposal pipeline (deferred — see issue #170)

---

## 1. Purpose

This paper defines the ShopManager — the Worker whose single job is
supervising other Workers.

---

## 2. Definition

A ShopManager is a Worker. Its mandate is supervision. It does not
perform domain work. It does not create Proposals for code changes.
Its only constitutional power is to detect problems and escalate.

ShopManagers declare `identity.class: supervision` in their `.intent/workers/`
YAML. This class is reserved for ShopManagers and distinguishes them from
sensing, acting, and governance Workers. No Worker outside this paper's
scope may declare `class: supervision`.

ShopManagers operate as a team. They monitor each other. A ShopManager
that goes silent triggers escalation from its peers.

---

## 3. What ShopManagers Monitor

ShopManagers read the Blackboard. They do not contact Workers directly.

Three supervisory responsibilities, each held by a dedicated ShopManager:

**Worker health and liveness**
- Detects Workers that have not posted a heartbeat within SLA.
- Detects Workers with claimed findings that have exceeded their SLA.
- Posts a `worker.silent::{worker_uuid}` finding when a Worker is silent.
- Posts a `blackboard.entry_stale::{entry_id}` finding when an entry
  is stale.

**Blackboard integrity and ledger health**
- Counts non-terminal entries.
- Detects entries that have been in `claimed` status beyond SLA.
- Detects duplicate findings for the same subject.

**Proposal pipeline health** *(Not Yet Implemented — see issue #170)*
- Detects Proposals stuck in `approved` status (ConsumerWorker not running).
- Detects Proposals stuck in `executing` status (execution interrupted).
- Detects repeated failures for the same action/rule combination.

A seed for condition (a)'s detection logic exists in
`src/cli/resources/runtime/health.py:439-448` as a manual CLI query. That
SQL is the starting point for the eventual ProposalPipelineShopManager;
it is not yet a constitutional carrier because it does not run on a
schedule, post Blackboard findings, or read its threshold from `.intent/`.

The other two responsibilities (Worker health, Blackboard integrity) are
implemented and active. Until the proposal-pipeline ShopManager exists,
the human architect must directly inspect proposal-pipeline state via the
`core-admin runtime health` CLI command.

---

## 3a. Implementation Status

| Responsibility            | Status   | Implementing Worker            |
| ------------------------- | -------- | ------------------------------ |
| Worker health & liveness  | active   | `worker_shop_manager`          |
| Blackboard integrity      | active   | `blackboard_shop_manager`      |
| Proposal pipeline health  | deferred | `proposal_pipeline_shop_manager` (planned, issue #170) |

This table is the authoritative implementation map. Drift between this
table and the contents of `.intent/workers/` is itself a finding the
constitutional coherence audit will surface.

---

## 4. Escalation Model

When a ShopManager detects a condition it cannot resolve by posting a
finding, it escalates to the Human.

Escalation is a Blackboard entry of type `report` with subject
`shopmanager.escalation::{condition}`.

### 4a. Human Notification Channel

Escalation entries on the Blackboard are the authoritative record.
The human notification channel is declared in
`.intent/enforcement/config/governance_paths.yaml` under
`escalation.notification_channel`. Supported channels:

- `log` — escalation is written to the daemon log at ERROR level.
  The human monitors logs. This is the default.
- `file` — escalation is written to `var/escalations/{timestamp}.json`.
  The human monitors the escalations directory.

The channel is read at daemon startup. If the key is absent,
`log` is the default. The channel is not configurable at runtime.

### 4b. Human Authority and Resolution

The human architect has full authority over escalated conditions.
When the human resolves an escalation:

1. The underlying condition is corrected directly (restart a Worker,
   release a stale claim, fix a broken action, edit `.intent/`).
2. The escalation Blackboard entry is marked `resolved` by the human
   via `core-admin blackboard resolve {entry_id}`.
3. Normal autonomous operation resumes on the next daemon cycle.

The ShopManager does not wait for resolution. It continues monitoring
and will re-escalate if the condition persists beyond the next check
cycle.

### 4c. Escalation State Machine

```
posted (open) → acknowledged (claimed by human via CLI) → resolved
             ↘ re-escalated (condition persists after SLA)
```

A condition that has been escalated and not resolved within
`escalation.re_escalation_interval` (declared in `governance_paths.yaml`,
default 3600 seconds) is re-escalated with an updated entry referencing
the original escalation ID.

---

## 5. Self-Supervision

ShopManagers monitor each other via the same heartbeat mechanism they
use to monitor Workers. A ShopManager that goes silent is itself a
finding — posted by its peers via the standard `worker.silent::*`
subject. The `WorkerShopManager` is therefore the carrier of
self-supervision: it observes the entire registered worker population,
including the other supervisory workers and itself.

If the entire supervisory team goes silent simultaneously, CORE cannot
self-heal. This condition requires direct human intervention — check the
daemon process, inspect logs, and restart if necessary.

---

## 6. Non-Goals

This paper does not define:
- automatic recovery actions beyond claim release (see CORE-Blackboard.md §7a)
- ShopManager scheduling frequency (declared in worker YAML)
- the implementation of notification channel integrations beyond log and file
- the implementation of `proposal_pipeline_shop_manager` — its design,
  thresholds, and posting contract are deferred to the work tracked in
  issue #170
