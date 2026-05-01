<!-- path: .specs/papers/CORE-Blackboard.md -->

# CORE — The Blackboard

**Status:** Canonical
**Authority:** Constitution
**Scope:** All Worker coordination in CORE

---

## 1. Purpose

This paper defines the Blackboard — the shared ledger that is the only
communication channel between Workers.

---

## 2. Definition

The Blackboard is a persistent, append-oriented ledger stored in
`core.blackboard_entries`. Every Worker reads from it and writes to it.
No Worker communicates with another Worker directly.

The Blackboard is infrastructure. The constitution governs behavior around
it, not the Blackboard itself.

---

## 3. Schema

Every entry in the Blackboard has exactly these fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Permanent identity of this entry. Never reused. |
| `worker_uuid` | UUID | UUID of the Worker that created this entry. Must match a registered Worker. |
| `entry_type` | text | The kind of entry. See section 4. |
| `phase` | text | The constitutional Phase the Worker was in when posting. |
| `status` | text | Current lifecycle status. See section 5. |
| `subject` | text | What this entry is about. See section 6. |
| `payload` | jsonb | Entry-specific structured data. |
| `claimed_by` | UUID | UUID of the Worker that claimed this entry. Null until claimed. Set atomically with status=claimed. Cleared to null when status returns to open via release. Must equal the claiming Worker's worker_uuid. No other value is valid. |
| `claimed_at` | timestamp | When this entry was claimed. Null until claimed. |
| `resolved_at` | timestamp | When this entry reached a terminal status. |
| `created_at` | timestamp | When this entry was created. Immutable. |
| `updated_at` | timestamp | When this entry was last modified. |

---

## 4. Entry Types

Every Blackboard entry has exactly one entry type.

| Type | Who posts it | What it means |
|------|-------------|---------------|
| `finding` | Sensing Workers | A violation or condition requiring attention. |
| `report` | Any Worker | A completion record. Documents what a Worker did. |
| `heartbeat` | Any Worker | Proof of liveness. Posted at the start of every `run()`. |
| `claim` | Acting Workers | Declaration that a Worker has taken ownership of a finding. |
| `proposal` | Acting Workers | Record of a Proposal created from one or more findings. |

A Worker that completes work without posting a report has violated its
history obligation. Silence is a constitutional violation.

---

## 5. Status Lifecycle

Every entry moves through statuses in one direction only. The canonical
status values are declared in `.intent/META/enums.json` under
`blackboard_entry_status`. No status value outside that declaration is
valid.

```
open → claimed → resolved
              ↘ abandoned
              ↘ deferred_to_proposal
              ↘ dry_run_complete
              ↘ indeterminate
```

| Status | Terminal | Meaning |
|--------|----------|---------|
| `open` | No | Posted. Not yet claimed by any Worker. |
| `claimed` | No | Atomically claimed by exactly one Worker. |
| `resolved` | Yes | Successfully processed. |
| `abandoned` | Yes | Processing failed or was interrupted. |
| `deferred_to_proposal` | Yes | A Proposal was created for this finding. See section 5a. |
| `dry_run_complete` | Yes | Finding was evaluated in dry-run mode. No fix was applied. |
| `indeterminate` | Yes | Confidence too low to act. Requires human review. See section 5b. |

Non-terminal statuses are `open` and `claimed`. A Worker claiming findings
MUST filter to these values only.

### 5a. deferred_to_proposal revival

`deferred_to_proposal` is terminal at the finding level, but the downstream
Proposal may fail. If a Proposal reaches `failed` status, the ProposalConsumerWorker
MUST reopen all findings that were marked `deferred_to_proposal` by that
Proposal by setting their status back to `open` and clearing `claimed_by`.
This ensures the remediation loop can reclaim them on the next cycle.

### 5b. indeterminate exit

An `indeterminate` finding requires explicit human action to exit. The
architect reviews the finding, makes a determination, and either:
- Sets status to `open` to re-enter the remediation loop, or
- Sets status to `abandoned` to permanently close it.

No automated Worker may transition an `indeterminate` finding without
explicit human authorization recorded in the finding's payload.

---

## 6. Subject Convention

The subject field is a structured string identifying what the entry is about.

Format: `namespace::qualifier::identifier`

### Finding subjects

```
audit.violation::{rule_id}::{file_path}
```

Example: `audit.violation::style.import_order::src/body/workers/violation_remediator.py`

### Proposal subjects

```
proposal::{action_id}::{scope_key}
```

Where `scope_key` is the primary affected file path, or the action group
identifier when multiple files are in scope. Example:
`proposal::fix.imports::src/body/workers/violation_remediator.py`

### Report and heartbeat subjects

```
audit.remediation.complete::{file_path}
audit.remediation.dry_run::{file_path}
audit.remediation.failed::{file_path}
worker.heartbeat
worker.error
shopmanager.escalation::{worker_uuid}
```

The subject is the primary key for deduplication. Before posting a Finding,
a Worker checks whether an entry with the same subject already exists in a
non-terminal status. If it does, the Finding is skipped.

---

## 7. Claim Atomicity

Claim operations use `FOR UPDATE SKIP LOCKED`.

This means: when multiple Workers attempt to claim the same finding
simultaneously, exactly one succeeds. The others skip it and move on.
There is no retry, no queue, no message broker. The database lock is
the coordination mechanism.

A Worker that claims a finding and then fails to process it must mark
it `abandoned`. It must not leave it in `claimed` status indefinitely.
A claimed entry that is never resolved or abandoned is a governance
violation — it blocks all other Workers from acting on that finding.

---

## 7a. Dead Worker Recovery

If a Worker terminates while holding claimed entries, those entries remain
in `claimed` status indefinitely, blocking the remediation loop. Recovery
is handled as follows:

- The ShopManager detects Workers whose last heartbeat exceeds their declared
  SLA plus glide-off period.
- For each silent Worker, the ShopManager queries all Blackboard entries where
  `claimed_by = {worker_uuid}` and `status = 'claimed'`.
- Each such entry is reset to `status = 'open'`, `claimed_by = NULL`,
  `claimed_at = NULL`.
- A `report` entry is posted recording the recovery action, the Worker UUID,
  and the count of released entries.

No human action is required for dead-worker recovery. The ShopManager
executes it autonomously within its governance authority.

---

## 8. SLA by Entry Type

Entries that remain in non-terminal status beyond their SLA are flagged
by the ShopManager as stale.

| Entry type | SLA |
|------------|-----|
| `heartbeat` | 120 seconds |
| `finding` | 3600 seconds |
| `report` | 3600 seconds |
| `proposal` | 7200 seconds |
| default | 3600 seconds |

A Worker that does not post a heartbeat within its SLA is considered
silent. Silence is a constitutional signal — the ShopManager escalates.

---

## 9. What the Blackboard Does Not Do

The Blackboard does not:
- route messages between Workers
- notify Workers of new entries
- enforce ordering beyond creation timestamp
- guarantee delivery

Workers poll. Workers claim. Workers act. The Blackboard records.

---

## 10. Non-Goals

This paper does not define:
- the database schema migration
- indexing strategy
- retention or archival policy
- the ShopManager's monitoring queries

Those are implementation concerns.
