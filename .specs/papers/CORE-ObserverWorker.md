---
kind: paper
id: CORE-ObserverWorker
title: CORE — Observer Worker
status: canonical
doctrine_tier: informational
---

<!-- path: .specs/papers/CORE-ObserverWorker.md -->

# CORE — Observer Worker

**Status:** Canonical
**Authority:** Policy
**Scope:** Continuous system health observation

---

## 1. Purpose

This paper defines the `ObserverWorker` — the sensing Worker responsible for
producing a structured system situation report on a fixed schedule.

---

## 2. Definition

`ObserverWorker` is a sensing Worker. It reads system state across all
constitutional domains, posts a structured situation report to the Blackboard,
and writes to `core.system_health_log`. It makes no decisions. It calls no LLM.
It writes no source files.

The `core-admin runtime health` command surfaces the health log written by this
worker. `ObserverWorker` is the upstream producer that makes continuous health
trend visibility possible.

---

## 3. Constitutional Identity

| Field | Value |
|---|---|
| Declaration | `.intent/workers/observer_worker.yaml` |
| Class | `sensing` |
| Phase | `audit` |
| Permitted tools | none |
| Approval required | false |
| Schedule | max_interval 300 s (5 min), glide_off 30 s |

---

## 4. Pipeline Status

**Paused.** Implementation is complete. No LLM dependency — pure deterministic
DB reads. Held pending confirmation that the daemon is running stably and
continuous health trend visibility is needed. Activate when the daemon has
sustained stable operation and `core-admin runtime health` output is desired
to be driven continuously rather than on-demand.

---

## 5. Output Surfaces

| Surface | Nature |
|---|---|
| Blackboard | Situation report posted as a report entry |
| `core.system_health_log` | Structured health record consumed by `core-admin runtime health` |

---

## 6. Non-Goals

This paper does not define:
- the schema of the situation report payload
- alerting thresholds or escalation logic
- remediation of health findings

---

## 7. Amendment Discipline

This paper may be amended only by explicit constitutional replacement, in
accordance with the CORE amendment mechanism.
