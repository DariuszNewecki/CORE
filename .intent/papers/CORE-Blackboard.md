<!-- path: .intent/papers/CORE-Blackboard.md -->

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
| `claimed_by` | UUID | UUID of the Worker that claimed this entry. Null until claimed. |
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

Every entry moves through statuses in one direction only.

open → claimed → resolved
↘ abandoned

| Status | Meaning |
|--------|---------|
| `open` | Posted. Not yet claimed by any Worker. |
| `claimed` | Atomically claimed by exactly one Worker. No other Worker may claim it. |
| `resolved` | Successfully processed. Terminal. |
| `abandoned` | Processing failed or was interrupted. Terminal. |

Terminal statuses are permanent. A resolved or abandoned entry is never
reopened. If the same condition recurs, a new Finding is posted.

---

## 6. Subject Convention

The subject field is a structured string identifying what the entry is about.

Format: `namespace::qualifier::identifier`

Examples:
- `audit.violation::style.import_order::src/body/workers/violation_remediator.py`
- `audit.remediation.complete::src/body/workers/violation_remediator.py`
- `audit.remediation.dry_run::src/body/workers/violation_remediator.py`
- `audit.remediation.failed::src/body/workers/violation_remediator.py`
- `worker.heartbeat`
- `worker.error`

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
