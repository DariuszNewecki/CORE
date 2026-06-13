---
kind: paper
id: CORE-DbSyncWorker
title: CORE — DB Sync Worker
status: canonical
doctrine_tier: informational
---

<!-- path: .specs/papers/CORE-DbSyncWorker.md -->

# CORE — DB Sync Worker

**Status:** Canonical
**Authority:** Policy
**Scope:** Scheduled PostgreSQL knowledge graph synchronization

---

## 1. Purpose

This paper defines the `DbSyncWorker` — the acting Worker responsible for
keeping the PostgreSQL knowledge graph current on a fixed schedule.

---

## 2. Definition

`DbSyncWorker` is a thin, deterministic wrapper around the `sync.db` atomic
action. It delegates all transformation work to `ActionExecutor` and contributes
nothing of its own beyond scheduling and Blackboard reporting. No LLM. No file
writes. No Blackboard claims.

The worker exists because `sync.db` was previously operator-triggered via
`core-admin dev sync --write`. Automating that trigger as a scheduled worker
removes the operator from the synchronization loop while preserving the same
atomic action and its governance.

---

## 3. Constitutional Identity

| Field | Value |
|---|---|
| Declaration | `.intent/workers/db_sync_worker.yaml` |
| Class | `acting` |
| Phase | `execution` |
| Permitted tools | `sync.db` |
| Approval required | false |

---

## 4. Blackboard Contract

| Subject | Entry type | Condition |
|---|---|---|
| `sync.db.complete` | report | `sync.db` returned `ok=True` |
| `sync.db.failed` | finding | `sync.db` returned `ok=False` or raised |

---

## 5. Design Rationale

The worker is intentionally thin. The `sync.db` action carries its own
governance (ConservationGate, IntentGuard, Canary). Embedding synchronization
logic in the worker would duplicate the action's responsibility. The worker's
only contribution is: run this action on a schedule and make the result visible
on the Blackboard.

---

## 6. Non-Goals

This paper does not define:
- what `sync.db` does or how it synchronizes the knowledge graph
- the knowledge graph schema or its consumers
- how `core-admin dev sync --write` interacts with this worker

---

## 7. Amendment Discipline

This paper may be amended only by explicit constitutional replacement, in
accordance with the CORE amendment mechanism.
