---
kind: paper
id: CORE-Blackboard-State-Machine
title: CORE — Blackboard Entry State Machine
status: canonical
doctrine_tier: constitution
---

<!-- path: .specs/papers/CORE-Blackboard-State-Machine.md -->

# CORE — Blackboard Entry State Machine

**Status:** Canonical
**Authority:** Constitution; ADR-045, ADR-069, ADR-072, ADR-091
**Scope:** `core.blackboard_entries` lifecycle
**Companion:** `CORE-Blackboard.md` (schema, SLA, claim atomicity)

---

## 1. Purpose

`CORE-Blackboard.md` defines the schema, entry types, and coordination
model. This paper defines the state machine: every status value, every
legal transition, the guards that protect them, and the invariants that
enforce them. Together the two papers are the complete constitutional
specification for `core.blackboard_entries`.

---

## 2. Status Vocabulary

The canonical status vocabulary is declared in
`.intent/META/enums.json` under `blackboard_entry_status`. No value
outside this declaration is legal. Current members:

```
open, claimed, awaiting_reaudit,
resolved, abandoned, deferred_to_proposal,
dry_run_complete, indeterminate, suppressed
```

Nine values. Three categories:

| Category | Values | Workers may claim? |
|----------|--------|-------------------|
| Active — claimable | `open`, `claimed` | Yes |
| Active — non-claimable | `awaiting_reaudit` | No — awaiting sensor adjudication |
| Terminal | `resolved`, `abandoned`, `deferred_to_proposal`, `dry_run_complete`, `indeterminate`, `suppressed` | No |

The claimable set is `{open, claimed}`. Worker claim queries MUST
filter to exactly these two values. `awaiting_reaudit` is non-terminal
but excluded from the claimable set because the finding's truth claim
is under re-evaluation by the owning sensor — no worker may act on it
until the sensor adjudicates it. (ADR-045; `blackboard_entry_status_active`
in enums.json.)

---

## 3. The `resolution_mechanism` Field

Every `entry_type='finding'` row carries a `resolution_mechanism`
column that declares which authority class may transition the finding
to a terminal state. The vocabulary is:

| Value | Closing authority | `awaiting_reaudit` eligible |
|-------|------------------|-----------------------------|
| `reaudit` | The owning audit/sensor worker, after re-evaluating the subject's truth claim | **yes** |
| `self_resolve` | The finding resolves itself when the underlying condition disappears | no |
| `human` | Explicit governor action required | no |

`resolution_mechanism` is orthogonal to the `abandoned`/`suppressed`
re-emission axis (§6). It does not control what happens after a
terminal state; it controls which authority class may close an open
finding. The two axes never interact.

A transition that changes which authority class may close a finding
**owns** `resolution_mechanism` — the transition must update the field
to match the new authority. This is the ADR-091 D2 Amendment invariant.

---

## 4. State Transition Diagram

```
                        ┌──────────────────────────────────────┐
                        │             ACTIVE                   │
                        │                                      │
       post_finding()   │    claim()          resolution       │
            ○ ─────────►│    open ──────────► claimed ──────►  ├─► resolved (terminal)
                        │      ▲                  │  ╲──────►  ├─► abandoned (terminal)
                        │      │                  │  ╲──────►  ├─► deferred_to_proposal (terminal)
                        │      │                  │  ╲──────►  ├─► dry_run_complete (terminal)
                        │      │                  │  ╲──────►  ├─► indeterminate (terminal)
                        │      │                  │            │
                        │      │         on Proposal           │
                        │      │         failure/rejection     │
                        │      │    awaiting_reaudit ◄─────────┘  deferred_to_proposal
                        │      │         │                     │
                        │      └─────────┘  (drainer clears)  │
                        │              ╲──────────────────────►├─► resolved (terminal)
                        │                                      │
                        └──────────────────────────────────────┘

  Any non-terminal status → suppressed   (governor action only)
  indeterminate → open                   (governor re-enters)
  indeterminate → abandoned              (governor closes)
```

---

## 5. Transitions — Legal and Guards

### 5.1 `open → claimed`

**Actor:** Any Worker permitted to claim this entry type.
**Mechanism:** `SELECT … FOR UPDATE SKIP LOCKED` — exactly one worker
wins when multiple attempt simultaneously. The row is updated atomically:
`status = 'claimed'`, `claimed_by = {worker_uuid}`,
`claimed_at = now()`, `lease_expires_at = now() + {lease_duration}`
(ADR-069 D1/D2).
**Guard:** Worker MUST NOT attempt to claim an `awaiting_reaudit` entry.
Claim queries MUST filter to `status IN ('open', 'claimed')`.

**Aspirational status:** Enforcing rule not yet authored; this is normative design intent.

### 5.2 `claimed → resolved`

**Actor:** The claiming worker, on successful completion.
**Meaning:** The condition the finding described has been remediated or
verified. No further action is required.
**Guard:** `resolved_at` is set to `now()`. `claimed_by` is not cleared
(forensic attribution).

### 5.3 `claimed → abandoned`

**Actor:** The claiming worker on unrecoverable failure; or the
ShopManager on lease expiry (ADR-069); or the ShopManager on dead-worker
recovery (CORE-Blackboard.md §7a).
**Meaning:** Processing failed or was interrupted. The finding may be
re-emitted by its sensor on the next detection cycle.
**Guard:** A Worker that cannot complete processing MUST transition
to `abandoned`; it MUST NOT leave the row in `claimed`. A claimed
row with an expired `lease_expires_at` is eligible for re-claim by
any permitted worker after the ShopManager releases it.

**Aspirational status:** Enforcing rule not yet authored; this is normative design intent.

### 5.4 `claimed → deferred_to_proposal`

**Actor:** The RemediatorWorker, after creating a Proposal for this
finding.
**Meaning:** Remediation work has been delegated to the proposal
pipeline. The finding is terminal at the finding level; the downstream
Proposal continues the work.
**Revival contract:** If the Proposal reaches `failed` or is `rejected`,
the ProposalConsumerWorker MUST transition matched findings from
`deferred_to_proposal` to `awaiting_reaudit` (not directly to `open`).
This prevents the remediator from immediately re-claiming a finding
whose content may be stale. (ADR-045.)

### 5.5 `claimed → dry_run_complete`

**Actor:** Any Worker executing in dry-run mode.
**Meaning:** The finding was evaluated; no change was applied to the
working tree. Dry-run results are recorded in the payload.

### 5.6 `claimed → indeterminate`

**Actor:** Any Worker whose confidence falls below the action threshold.
**Meaning:** The finding requires human governor review before any
automated action is taken.
**Guard (blocking rule `architecture.blackboard.indeterminate_requires_human_mechanism`):**
The transition MUST co-assign `resolution_mechanism = 'human'` in
the same SET clause. A row entering `indeterminate` with `resolution_mechanism = 'reaudit'`
would be invisible to ADR-045's automated re-evaluation path (no sensor
owns its truth claim) and would re-surface as a fresh finding every
audit cycle. (ADR-091 D2 Amendment.)

**Aspirational status:** Enforcing rule not yet authored; this is normative design intent.

### 5.7 `deferred_to_proposal → awaiting_reaudit`

**Actor:** ProposalConsumerWorker, on Proposal `failed` or `rejected`.
**Meaning:** Proposal-level remediation did not succeed; the finding
is parked for the owning sensor to re-evaluate whether the underlying
violation still holds.
**Guard (blocking rule `architecture.blackboard.reaudit_requires_reaudit_mechanism`):**
The UPDATE MUST include `WHERE resolution_mechanism = 'reaudit'` in
the same clause. A `self_resolve` or `human` finding MUST NOT enter
`awaiting_reaudit` — no sensor owns its subject prefix, so it could
never exit. (ADR-045; ADR-091 Revision B.)
**Drainer invariant (ADR-072):** Every subject namespace that admits
`awaiting_reaudit` rows MUST have a registered drainer in
`.intent/enforcement/quarantine/drainer_registry.yaml`. A namespace
without a drainer accumulates entries that can never exit. The rule
`governance.quarantine.namespace_has_drainer` enforces this at audit
time.

### 5.8 `awaiting_reaudit → open`

**Actor:** The drainer worker registered for this finding's subject
namespace.
**Meaning:** The drainer re-evaluated the rule and found the violation
still holds. The finding is returned to the claimable pool.
**Guard:** Only the owning drainer may perform this transition.
`resolution_mechanism` stays `'reaudit'`.

### 5.9 `awaiting_reaudit → resolved`

**Actor:** The drainer worker registered for this finding's subject
namespace.
**Meaning:** The drainer re-evaluated the rule and found the violation
no longer holds (the subject no longer exists, or the code was fixed
independently). `resolved_at` is set.

### 5.10 Non-terminal → suppressed (governor action)

**Actor:** Governor.
**Meaning:** The governor has permanently silenced this subject. The
sensor that emits this finding's subject prefix MUST skip it on every
future detection cycle. Unlike `abandoned` (sensor MAY re-emit on
fresh detection), a `suppressed` subject MUST NOT be re-emitted.
**Guard:** No automated worker may transition a finding to `suppressed`.
This is a deliberate governor action.

**Aspirational status:** Enforcing rule not yet authored; this is normative design intent.

### 5.11 `indeterminate → open` (governor action)

**Actor:** Governor.
**Meaning:** After reviewing the finding, the governor determines it is
valid and the finding should re-enter the automated remediation loop.
`resolution_mechanism` is restored to the appropriate value (`'reaudit'`
or `'self_resolve'`) to match the intended closing authority.

### 5.12 `indeterminate → abandoned` (governor action)

**Actor:** Governor.
**Meaning:** After reviewing the finding, the governor closes it as
unactionable. No re-emission is expected unless the sensor detects a
fresh instance of the same condition.

---

## 6. Re-emission Semantics — `abandoned` vs `suppressed`

The `abandoned` / `suppressed` axis governs what the *sensor* does
after a finding enters a terminal state. It is orthogonal to
`resolution_mechanism` (§3) and does not overlap with lifecycle
transitions.

| Terminal status | Sensor MAY re-emit on next detection? |
|----------------|--------------------------------------|
| `resolved` | No — the condition was fixed. |
| `abandoned` | Yes — workers gave up; the underlying issue may persist. |
| `suppressed` | No — governor signal: this subject is permanently silenced. |
| `deferred_to_proposal` | No — the Proposal pipeline takes over. |
| `dry_run_complete` | Depends on sensor design. |
| `indeterminate` | No — awaiting governor action. |

---

## 7. Insert Authority

INSERT against `core.blackboard_entries` MUST originate from the
Worker base class at `src/shared/workers/base.py`.

Non-Worker code (services, atomic actions, API handlers) posts through
the Worker methods `self.post_finding()`, `self.post_report()`,
`self.post_heartbeat()`. These helpers apply ASCII sanitization, route
to `BlackboardPublisher._post_entry()`, and enforce the subject
deduplication contract.

Direct INSERT from outside the Worker base class is a constitutional
violation (`architecture.blackboard.worker_only_inserts`).

**Enforced by:** `.intent/rules/architecture/blackboard.json` → `architecture.blackboard.worker_only_inserts` (blocking).

---

## 8. Transition Authority Summary

| Transition | Who may perform it |
|-----------|-------------------|
| `open → claimed` | Any permitted Worker (via `FOR UPDATE SKIP LOCKED`) |
| `claimed → {resolved, abandoned, deferred_to_proposal, dry_run_complete, indeterminate}` | The claiming Worker |
| `claimed → abandoned` | ShopManager (lease expiry, dead-worker recovery) |
| `deferred_to_proposal → awaiting_reaudit` | ProposalConsumerWorker |
| `awaiting_reaudit → open` | Registered drainer Worker for the subject namespace |
| `awaiting_reaudit → resolved` | Registered drainer Worker for the subject namespace |
| Any non-terminal → `suppressed` | Governor only |
| `indeterminate → open` | Governor only |
| `indeterminate → abandoned` | Governor only |

---

## 9. Blocking Invariants

Three blocking rules govern the state machine at the SQL surface
(`.intent/rules/architecture/blackboard.json`):

**`architecture.blackboard.worker_only_inserts`** — INSERT MUST
originate from the Worker base class. Services route through Worker
posting helpers.

**`architecture.blackboard.reaudit_requires_reaudit_mechanism`** —
Every UPDATE that transitions a row to `status = 'awaiting_reaudit'`
MUST include `WHERE … resolution_mechanism = 'reaudit'` in the same
clause. Enforces that only reaudit-eligible findings enter the
quarantine queue.

**`architecture.blackboard.indeterminate_requires_human_mechanism`** —
Every UPDATE that transitions a row to `status = 'indeterminate'`
MUST co-assign `resolution_mechanism = 'human'` in the SET clause.
Enforces ADR-091 D2 Amendment: a transition that changes closing
authority owns the field.

One advisory rule governs the namespace level:

**`governance.quarantine.namespace_has_drainer`** (ADR-072, currently
advisory; path to blocking per ADR-072 D5) — every subject namespace
with `awaiting_reaudit` rows MUST have a registered drainer in
`.intent/enforcement/quarantine/drainer_registry.yaml`. A namespace
without a drainer cannot drain to zero; its findings accumulate
indefinitely.

---

## 10. References

- `CORE-Blackboard.md` — schema, SLA, claim atomicity, entry types
- `CORE-Workers-and-Governance-Model.md` — Worker mandate and posting obligations
- ADR-045 — `awaiting_reaudit` quarantine state and revival contract
- ADR-069 — Claim-as-lease semantics; `lease_expires_at`
- ADR-072 — Drainer registry invariant; `governance.quarantine.namespace_has_drainer`
- ADR-091 Revision B / D2 Amendment — `resolution_mechanism` field and
  closing-authority invariants
- `.intent/META/enums.json` `blackboard_entry_status` — canonical status vocabulary
- `.intent/META/enums.json` `blackboard_entry_status_active` — claimable subset
- `.intent/enforcement/quarantine/drainer_registry.yaml` — registered drainers
