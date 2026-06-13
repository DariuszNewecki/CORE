---
kind: adr
id: ADR-103
title: ADR-103 — Worker `schedule.max_interval` is a cycle cap, not a sleep cap
status: accepted
---

<!-- path: .specs/decisions/ADR-103-worker-max-interval-is-cycle-cap.md -->

# ADR-103 — Worker `schedule.max_interval` is a cycle cap, not a sleep cap

**Date:** 2026-06-09
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-09 — drafted under explicit "you may write it" authorization at the close of a recon on `db_sync_worker`'s live BLOCK. Recon confirmed that the runtime sleep math at `src/cli/commands/daemon.py:174` and `src/will/workers/worker_shop_manager.py:138` is already cycle-cap arithmetic — `sleep(max(interval - elapsed, 0))` makes the next cycle start at `max(elapsed, interval)`. The "split semantics" #604 surfaced exists in *documentation*, not in mechanism. This ADR pins the contract the runtime already enforces.)
**Closes:** #604 (split semantics of `max_interval` across runtime, liveness, and rule sites)
**Grounding decisions:**
- ADR-041 — introduced `schedule.max_interval` as per-worker liveness threshold; semantics underspecified at the field's birth, which let three reading sites drift into three mental models.
- ADR-091 D2 — ramp arc that promoted `runtime.worker_max_interval_within_observed` from reporting to blocking; promotion exposed the residual ambiguity #604 names.
- ADR-081 D2(1) — empirical 5s loop-hold gate for `requires_dedicated_process: true`; ruled out by #604 as the wrong remedy for the workers that triggered this analysis.

**Related:**
- #516 — original filing for the `worker_max_interval_within_observed` rule (9,125 `worker.silent` false-positives that motivated it).
- #604 — the meta-finding this ADR closes: three sites reading one field with three semantics.
- `.intent/rules/runtime/worker_max_interval.json` — the rule; its rationale already articulates cycle semantics, so no logic change.
- `src/shared/workers/schedule.py:111` — liveness threshold (`max_interval + glide_off`); shape unchanged, docstring re-framed.
- `src/cli/commands/daemon.py:174`, `src/will/workers/worker_shop_manager.py:138` — runtime sleep sites; math unchanged, comment added cross-referencing this ADR.
- Memory `[[feedback_two_surface_requires_two_structures]]` — invoked in #604: when one structure is being read in semantically incompatible ways, the unification was the bug. This ADR resolves the read-mode ambiguity without splitting the structure (the runtime mechanism is already consistent).
- Memory `[[feedback_three_layer_intent_alignment]]` — rule / check / engine convention must agree. Here the three sites are runtime / liveness / rule, and the alignment is achieved by pinning the contract, not by changing math.

---

## Context

### The split lives in documentation, not mechanism

`schedule.max_interval` is read by three sites today, with three implicit mental models:

| Site | File | Implicit model |
|---|---|---|
| Shared-loop runtime | `src/cli/commands/daemon.py:174` | Sleep cap (operator: "wake the worker every N") |
| Per-worker `run_loop` (manager workers) | `src/will/workers/worker_shop_manager.py:138` | Sleep cap |
| Liveness threshold | `src/shared/workers/schedule.py:111` | Cycle cap (`max_interval + glide_off` = "stale after this") |
| Rule | `.intent/rules/runtime/worker_max_interval.json` + `runtime_gate` | Cycle cap × 1.1 (observed p95 vs configured) |

When `work ≪ max_interval`, all three readings collapse to the same number — the worker sleeps almost the whole interval, so sleep ≈ cycle. As work grows even modestly, they diverge. The rule fires on the divergence.

#604's analysis read the runtime as "sleep cap" because the literal `sleep()` argument is `interval - elapsed`. **That reading is wrong on closer inspection.** The math `sleep(max(interval - elapsed, 0))` means:

- If work took `W` seconds and `W < interval`, next cycle starts at `t = interval` exactly.
- If work took `W ≥ interval`, next cycle starts at `t = W` (cycle has slipped past the cap).

That is cycle-cap arithmetic: the operator is targeting cycle `t = interval`, and the runtime adapts sleep to honor it. The runtime is not measuring sleep and bounding it by `interval`; it is measuring elapsed work and bounding the *whole cycle* by `interval`.

So all three sites are already mechanically in agreement on a cycle-cap semantics. The mental-model divergence is documentation drift — `max_interval` was introduced by ADR-041 without a docstring pinning what an operator declares when they write a value, and three independent readers built three plausible models around it.

### The two-surface memory still applies, just not where #604 placed it

`[[feedback_two_surface_requires_two_structures]]` warns that unifying two semantically incompatible reads into one structure is the bug. The structure here (`max_interval`) is consistent; the two surfaces are *operator-facing semantics* (what does writing `60` mean?) and *runtime mechanism* (how is `60` enforced?). The mechanism never split. The semantics split silently because the operator-facing surface was never declared.

This ADR declares it.

### Why the alternative (Option A — make it a sleep cap) was rejected

#604 framed two coherent paths. Option A would change the rule and the liveness threshold to read the field as a sleep cap, leaving the runtime alone. That path:

- Requires *more* code change than Option B, not less — the rule's observation logic and the liveness threshold's arithmetic both move.
- Contradicts conventional scheduler precedent (cron, systemd timers, Kubernetes CronJob, Sidekiq, Prometheus `scrape_interval`, Kafka `heartbeat.interval.ms` — all cycle-cap).
- Absorbs cycle drift into a separately-governed tolerance budget (`glide_off`), hiding the operationally meaningful signal that work has grown past its budget.
- Forces operators to reason about cadence and liveness as decoupled concerns, when the simpler unified mental model ("max time between heartbeats") covers both.

Option B was selected by the governor; this ADR pins it.

---

## Decisions

### D1 — `schedule.max_interval` is the cycle cap (constitutional)

**Every active worker's `schedule.max_interval` declares the maximum acceptable time between consecutive cycle starts.** The operator writing `max_interval: 360` is declaring: *this worker shall begin a new cycle no less often than every 360 seconds.* All three reading sites MUST honor that contract:

- **Runtime sleep** enforces it by sleeping `max(max_interval - elapsed, 0)` between cycles. Already in force at `src/cli/commands/daemon.py:174` and `src/will/workers/worker_shop_manager.py:138`. No math change.
- **Liveness threshold** treats `max_interval + glide_off` as the deadline beyond which a missing heartbeat is `worker.silent`. Already in force at `src/shared/workers/schedule.py:111`. No math change.
- **Audit rule** (`runtime.worker_max_interval_within_observed`) treats `max_interval × 1.1` as the deadline beyond which observed p95 cycle is a constitutional drift signal. Already in force in `runtime_gate`. No math change.

The contract is the operator's declaration. The three reading sites are three independent enforcers of one contract, not three independent contracts.

### D2 — The 1.1 multiplier and `glide_off` are both jitter tolerance, not headroom

The rule's `× 1.1` and the liveness threshold's `+ glide_off` model **measurement jitter** — real-world variance from scheduler delays, occasional DB write latency, and event-loop scheduling under shared-loop concurrency. They are not:

- A tolerance budget the operator may spend.
- Headroom for work to grow into.
- A fudge factor masking systematic drift.

A finding from `runtime.worker_max_interval_within_observed` means observed p95 cycle has exceeded configured `× 1.1` — i.e., real work has grown past the cap, beyond what jitter accounts for. The operationally meaningful response is **investigate, then bump if and only if the new cycle reality is acceptable.** Reflexively bumping configured to match observed is documented as the rule's literal recommendation because operators sometimes need a fast clear, but it is not the structural response.

This pins the meaning of both tolerance structures without merging them. They serve the same semantic purpose at two different cadences (the rule's 24h aggregation window vs. the liveness check's per-heartbeat freshness) and stay as independent structures because the cadence difference is mechanically load-bearing.

### D3 — No mechanism change

This ADR adds zero lines of executable logic. The runtime, liveness check, and rule all already implement the cycle-cap contract; what was missing is a constitutional declaration of what they were implementing.

Implementation footprint:

- **`.specs/papers/`**: no paper change required. The cycle-cap contract is constitutional-grade but small; this ADR is the canonical source.
- **`.intent/workers/<stem>.yaml` schema description**: the description of `mandate.schedule.max_interval` in `META/worker.schema.json` is updated to read "max time between consecutive cycle starts (cycle cap)" with a cross-reference to ADR-103. Pure documentation.
- **`.intent/rules/runtime/worker_max_interval.json`**: rationale already articulates cycle semantics. Light touch: a sentence referencing ADR-103 as the contract this rule enforces.
- **`src/cli/commands/daemon.py:174` and `src/will/workers/worker_shop_manager.py:138`**: a one-line comment at each sleep site explaining the arithmetic is cycle-cap math per ADR-103. No math change.
- **`src/shared/workers/schedule.py:111`**: a one-line comment on `glide_off` framing it as jitter tolerance per ADR-103 D2. No math change.

### D4 — Tactical drift response stays tactical

When the rule fires, the operator's response is the same as today: bump `max_interval` in the worker's YAML to the rule's recommended value, with a comment in the YAML explaining what observed cycle data justified the bump. This ADR does not introduce a new escalation surface; it pins the contract under which those tactical bumps are reasoned about.

The `db_sync_worker` 360→420 bump clearing today's live BLOCK is the first tactical operation under the pinned contract. It is independent of this ADR and lands separately.

### D5 — What this ADR explicitly does NOT decide

To keep the ADR scoped:

- **Multiplier tuning.** The 1.1 factor in the rule and `glide_off` defaults in the liveness check stay at their current values. If post-ADR telemetry shows these are calibrated wrong for real-world jitter, that is a separate ADR (or, more likely, a separate operational tuning).
- **Multi-cycle scope creep detection.** A worker whose cycle has drifted upward over multiple weeks may indicate a structural problem (an embedder consuming a growing corpus, a sensor whose scan set has expanded). This ADR does not introduce a "cycle-growth-over-time" detector; it remains an open question whether such a thing is worth the telemetry cost. Filed as future work if the need surfaces.
- **The relationship between `max_interval` and `requires_dedicated_process: true`.** ADR-081 D2(1) governs that promotion under empirical loop-hold evidence. This ADR's cycle-cap pinning does not alter that gate. A worker whose cycle has grown past `max_interval` because of loop-hold contention is a candidate for ADR-081 D2(1) escalation, not for `max_interval` bumping.

---

## Consequences

### Closure

- #604 closes. The split semantics were a documentation gap; this ADR pins the contract the runtime already enforces.
- ADR-041's underspecified field is retroactively pinned. Future ADRs touching worker scheduling reference this ADR as the meaning of `max_interval`.

### Forward visibility

- Future workers inherit a single mental model. New `schedule.max_interval` declarations are written against a documented contract.
- A future reader of the runtime sleep math sees the cross-reference comment and does not re-derive the question.
- A `runtime.worker_max_interval_within_observed` finding is now unambiguously read as "real work has grown past the cap" rather than "the rule's threshold is too tight."

### Non-changes

- No code logic changes.
- No worker YAML value changes (`db_sync_worker` 360→420 is a separate tactical operation, not a consequence of this ADR).
- No new rules, no new fields, no new enforcement surfaces.

### Acceptance criteria

The ADR is satisfied when:

1. `META/worker.schema.json`'s description for `mandate.schedule.max_interval` references ADR-103 and reads as cycle cap.
2. `.intent/rules/runtime/worker_max_interval.json`'s rationale carries a one-sentence ADR-103 reference.
3. The two runtime sleep sites and the liveness threshold site each carry a one-line ADR-103 cross-reference comment.
4. #604 is closed with a pointer to this ADR.

These are documentation-only changes and land as one change-set after this ADR is accepted.
