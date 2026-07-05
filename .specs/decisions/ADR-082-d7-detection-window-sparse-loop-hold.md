---
kind: adr
id: ADR-082
title: "ADR-082 — D7 Detection Window for Sparse Loop-Hold Samples"
status: draft
depends_on: ["ADR-081"]
---

<!-- path: .specs/decisions/ADR-082-d7-detection-window-sparse-loop-hold.md -->

# ADR-082 — D7 Detection Window for Sparse Loop-Hold Samples

**Date:** 2026-07-05
**Status:** Accepted (governor decision 2026-07-05 — D1–D5 ratified. Implementation lands as one change-set.)
**Author:** Darek (Dariusz Newecki)
**Closes:** #597

**Governing ADR:**
- ADR-081 D2(1), D7, D8 Step 3a

---

## Context

ADR-081 D7 specifies the drift detector to fire `escalation_required` on a
`shares_process` worker whose observed **maximum** loop-hold time exceeds 5s
"in any cycle over a 5+ steady-state cycle window." The implementation in
`runtime_gate.py:_check_worker_process_classification` reads this as the last
N=5 blackboard samples (`ORDER BY created_at DESC LIMIT cycle_window * 4`,
then `durations[:cycle_window]`).

### Why rolling-N is wrong for event-driven sampling

`loop_hold.sample` rows are posted **only when `slow_callback_duration` is
tripped** — i.e., only when a slow event occurs. A worker that mostly behaves
and occasionally spikes produces a sparse stream. For such a worker:

- "Last 5 samples" can span hours or days.
- A single bad spike ages out of the window between D7 runs.
- The window never captures the worst recorded hold.

The 5-sample floor was intended as a noise floor against one-off GC spikes.
For event-driven sampling it is instead a staleness floor that lets perpetrators
hide behind recent good behavior.

### Live evidence (2026-07-05, 24h window)

Query: max and recent-5 per worker over the last 24h.

| Worker | 24h samples | 24h max (s) | Recent-5 max (s) | D7 verdict | Correct? |
|--------|------------|-------------|------------------|------------|----------|
| `db_sync_worker` | 101 | **17.77** | 9.42 | escalation_required | ✓ |
| `audit_ingest_worker` | 100 | **16.67** | 7.70 | escalation_required | ✓ |
| `audit_sensor_linkage` | 102 | **11.18** | 4.37 | **clean** | ✗ |
| `audit_sensor_modularity` | 102 | **8.67** | 4.60 | **clean** | ✗ |
| `audit_sensor_style` | 102 | **8.24** | 3.83 | **clean** | ✗ |
| `quality_ingest_worker` | 9 | **8.18** | 4.49 | **clean** | ✗ |
| `audit_sensor_logic` | 102 | **7.86** | 5.36 | escalation_required | ✓ (barely) |
| `audit_sensor_layout` | 102 | **7.76** | 4.06 | **clean** | ✗ |
| `audit_sensor_purity` | 104 | **7.72** | 3.93 | **clean** | ✗ |
| `proposal_consumer_worker` | 100 | **6.09** | 2.57 | **clean** | ✗ |
| `audit_sensor_governance` | 114 | **5.40** | 2.72 | **clean** | ✗ |
| `audit_sensor_architecture` | 106 | **5.22** | 3.73 | **clean** | ✗ |

Rolling-5 catches 2 of 12 workers with a 24h max above the 5s gate. Ten are
silently missed. The issue described in #597 is confirmed at scale.

Note: workers currently showing as dedicated (`requires_dedicated_process: true`)
appear in this list (the `audit_sensor_*` cluster). Their samples are still
posted; D7 reads them for de-escalation, not escalation. The misses are for
`proposal_consumer_worker`, `quality_ingest_worker`, and similar `shares_process`
workers with episodic high holds.

---

## Decisions

### D1 — Escalation: replace rolling-N with 24h time-bucketed window

The escalation criterion becomes: "max loop-hold sample observed in the last
`loop_hold_escalation_hours` exceeds `loop_hold_escalation_sec`."

**SQL change** (in `_check_worker_process_classification`):

```sql
-- Old
ORDER BY created_at DESC LIMIT :sample_cap
-- sample_cap = cycle_window * 4; then durations[:cycle_window]

-- New
WHERE created_at > now() - make_interval(hours => :escalation_hours)
ORDER BY created_at DESC
LIMIT 2000  -- safety cap; no semantic significance
```

**Skip-silently guard:** require at least `min_samples_for_escalation` (default
**3**) samples in the window before issuing a verdict. This replaces the 5-sample
floor from rolling-N. Rationale: 1–2 samples in a 24h window for an active
worker is suspicious (expected > 10 from the live data above); 3 is a conservative
floor that avoids false positives on workers that have been recently restarted.

**Gate unchanged:** max > `loop_hold_escalation_sec` (5.0s). The 5s perpetrator
definition from D2(1) is unchanged.

**Why 24h:** aligns with standard operational telemetry cycles; a worker that
monopolizes the loop once per day still wedges every peer during that stretch.
The evidence window from the #597 telemetry was 24h and surfaces the full
distribution cleanly.

### D2 — De-escalation: separate longer window + heartbeat activity check

The de-escalation criterion was symmetric with escalation under rolling-N. Under
time-bucketed windows it needs separate treatment because the semantics differ:

- **Escalation needs recency** (did this worker misbehave in the last day?).
- **De-escalation needs sustained cleanliness** (has this worker been quiet for
  long enough that we can safely propose demotion?). Demotion re-exposes peers
  to contention if the worker was misclassified; the evidence bar must be higher.

**New criterion for `deescalation_candidate`:**

1. Worker has been active: ≥ `min_active_heartbeats_for_deescalation` (default
   **10**) `worker.heartbeat` entries from this worker's UUID in the last
   `loop_hold_deescalation_hours`. This confirms the worker has been running —
   silence without heartbeats is not evidence of cleanliness.

2. Max loop-hold in the last `loop_hold_deescalation_hours` is below
   `loop_hold_deescalation_sec` (1.0s). Event-driven posting means **no samples
   = max is 0**, treated as below the gate. This is correct: silence from an
   event-driven instrument means the threshold was never tripped.

**New params:**
- `loop_hold_deescalation_hours: 168` (7 days, default)

Why 7 days: demotion is a higher-stakes decision than escalation. A dedicated
worker that had a bad day last week should not be a de-escalation candidate today.
7 days gives a week of clean evidence before surfacing the finding.

### D3 — Step 3a instrumentation: no change

Event-driven `loop_hold.sample` posting (only when `slow_callback_duration`
trips) is the **correct** instrument for escalation detection under this ADR —
every posted sample IS a slow-event observation. The time-bucketed window reads
all of them without needing periodic health-check samples.

Periodic sampling (per-coroutine, every N seconds regardless of hold time) was
mentioned in ADR-081 §170 as a "production-grade option." It would make rolling-N
work naturally but at higher instrumentation cost. That path is deferred; it is
not needed to fix the D7 detection gap.

### D4 — Threshold mathematics: gates unchanged

The 5s escalation gate and 1s de-escalation gate are D2(1)'s empirical perpetrator
definitions. They do not change with the window shape:

- With rolling-N: "5s seen in 5 most-recent samples"
- With time-bucket: "5s seen anywhere in the last 24h"

The time-bucket statement is strictly stronger evidence — it looks at the full
distribution over the period, not the most-recently-convenient 5 observations.
No threshold lifting is needed; if anything, the bucket makes the gate harder to
trip spuriously because the noise-floor is now 3 samples rather than 5 samples
in an arbitrarily-long window.

### D5 — Config migration: retire `cycle_window`, add new params

`WorkerClassificationConfig` in `shared/infrastructure/intent/operational_config.py`
gains three new fields and retires one:

| Field | Action | Default |
|-------|--------|---------|
| `loop_hold_escalation_sec` | unchanged | 5.0 |
| `loop_hold_deescalation_sec` | unchanged | 1.0 |
| `cycle_window` | **retired** | — |
| `loop_hold_escalation_hours` | **new** | 24 |
| `loop_hold_deescalation_hours` | **new** | 168 |
| `min_samples_for_escalation` | **new** | 3 |
| `min_active_heartbeats_for_deescalation` | **new** | 10 |

`operational_config.yaml`'s `worker_classification` block updated to match.
`cycle_window` removed in the same change-set (no interim compatibility shim
— CORE owns both the config and the consumer).

---

## Deliverables

| ID | Artifact | Description |
|----|---------|-------------|
| D1a | `src/shared/infrastructure/intent/operational_config.py` | Update `WorkerClassificationConfig` — retire `cycle_window`, add 4 new fields |
| D1b | `.intent/enforcement/config/operational_config.yaml` | Update `worker_classification` block |
| D1c | `src/mind/logic/engines/runtime_gate.py` | Replace rolling-N query with time-bucketed query; update de-escalation logic per D2 |
| Tests | `tests/mind/logic/engines/test_runtime_gate__worker_max_interval.py` | Update existing tests; add episodic-perpetrator and de-escalation-heartbeat cases |

Implementation order: D1a → D1b → D1c → Tests. One change-set.

---

## Consequences

**Immediate effect on running system:** switching to 24h time-bucket will fire
`escalation_required` on several workers currently seen as clean, including
members of the `audit_sensor_*` cluster. This is the correct behavior — they are
empirically confirmed to hold the loop above the gate. However, the `audit_sensor_*`
workers may already be classified `requires_dedicated_process: true` (they are
the ADR-081 Step 1 expected `true` set). The governor should verify current YAML
declarations before interpreting new findings; the check fires on
`shares_process` workers only.

**De-escalation sensitivity:** raising the evidence window from rolling-5-samples
to 7-days + 10 heartbeats means `deescalation_candidate` will fire less frequently.
This is intentional — demotion evidence should be harder to satisfy than escalation
evidence.

**No Step 3a changes:** the event-driven sample stream is unchanged; only the
consumer (D7) widens its window.
