<!-- path: .intent/papers/CORE-ShopManager.md -->

# CORE — ShopManager

**Status:** Canonical
**Authority:** Policy
**Scope:** Worker supervision

---

## 1. Purpose

This paper defines the ShopManager — the Worker whose single job is
supervising other Workers.

---

## 2. Definition

A ShopManager is a Worker. Its mandate is supervision. It does not
perform domain work. It does not create Proposals for code changes.
Its only constitutional power is to detect problems and escalate.

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

**Proposal pipeline health**
- Detects Proposals stuck in `approved` status (ConsumerWorker not running).
- Detects Proposals stuck in `executing` status (execution interrupted).
- Detects repeated failures for the same action/rule combination.

---

## 4. Escalation Model

When a ShopManager detects a condition it cannot resolve by posting a
finding, it escalates to the Human.

Escalation is a Blackboard entry of type `report` with subject
`shopmanager.escalation::{condition}`.

The Human is not in the loop for normal operations. Escalation is the
exception, not the rule.

---

## 5. Self-Supervision

ShopManagers monitor each other via the same heartbeat mechanism they
use to monitor Workers. A ShopManager that goes silent is itself a
finding — posted by its peers.

If the entire supervisory team goes silent simultaneously, CORE cannot
self-heal. This condition requires direct human intervention.

---

## 6. Non-Goals

This paper does not define:
- the human notification mechanism
- automatic recovery actions
- ShopManager scheduling frequency
