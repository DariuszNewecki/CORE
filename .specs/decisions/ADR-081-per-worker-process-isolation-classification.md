<!-- path: .specs/decisions/ADR-081-per-worker-process-isolation-classification.md -->

# ADR-081 — Per-worker process-isolation classification

**Date:** 2026-06-01
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-01 — drafted under Path A execute-verb authorization, "you write it, I review")
**Grounding paper:** `papers/CORE-Workers-and-Governance-Model.md` §3.1 (a Worker holds a mandate declared in `.intent/workers/`; existence in `.intent/workers/` is the sole source of constitutional standing — this ADR extends what the declaration governs to include the worker's runtime-process-isolation profile, on the same constitutional footing as its phase and schedule)
**Related:** Issue #518 (the framing motion this ADR formalizes), Issue #519 (graceful-shutdown lag — same root cause, verification signal for this ADR's implementation), Issue #516 / #517 (the `max_interval`-tuning thread that revealed per-worker tuning as the wrong layer), ADR-041 (per-worker liveness thresholds — the precedent this ADR follows for per-worker runtime properties), ADR-069 D8 (graceful claim-release in `Worker.start()` finally — the contract any future shutdown-bounding change must preserve)

---

## Context

### The measurement that reframed the problem

Issue #516 set out to tune `blackboard_shop_manager`'s `max_interval` against an observed cycle inflation. After the orphan-daemon contamination was cleared (commit `f55c83f9`) and a clean single-daemon baseline was measured, the worker-by-worker cycle-gap distribution revealed a structural problem:

| worker | declared | observed p50 | shape of work |
|---|---|---|---|
| `audit_sensor_architecture` | 1200s | 1927s | full-codebase AST walk |
| `audit_sensor_purity` | 1200s | 1347s | full-codebase AST walk |
| `audit_sensor_cli` | 1200s | 1252s | full-codebase AST walk |
| `governance_embedder` | 600s | 834s | embedding constitution docs |
| `blackboard_shop_manager` | 600s | 665–1155s | 5 SQL queries + N posts (trivial) |
| `violation_remediator` | 60s | 117s | small DB ops |
| `proposal_consumer_worker` | 60s | 111s | small DB ops |
| `test_remediator` | 60s | 117s | small DB ops |

Workers with trivial per-cycle CPU (sub-second SQL ops) observed 1.1–2× their declared interval. The cause is not what those workers do — it is what the *peer workers* in the same daemon do. Heavyweight CPU-bound workers (full-codebase AST walks) hold the single asyncio event loop long enough that `await asyncio.sleep(...)` in lightweight workers cannot fire on time. `blackboard_shop_manager`'s 1155s "cycle" is not 1155s of work; it is 1155s of waiting for the loop. (The `*_embedder` workers in the evidence table are also inflated, but for the opposite reason — they are victims of the AST-walker starvation, not perpetrators of it; their embed calls are network awaits on `httpx.AsyncClient` that release the loop, not CPU-bound monopolizers. See D2(2).)

Issue #519 documents the same root cause manifesting as graceful-shutdown lag: the daemon's SIGTERM handler is itself an asyncio callback, and it also waits for the next event-loop tick. Observed shutdowns reached the systemd `TimeoutStopUSec=1min 30s` ceiling and were SIGKILLed twice on 2026-06-01.

### What this means for tuning

Per-worker `max_interval` bumping (the original direction of #516 / #517) is the wrong instrument here. Raising a lightweight worker's `max_interval` masks the symptom (the worker no longer trips its liveness threshold) without changing the underlying reality (it still cannot fire on schedule, its constitutional cadence is still being decided by unrelated heavy workers, and a future drift in those heavy workers will require another tuning round). The lightweight worker's `max_interval` declaration was correct; the runtime is breaking the contract.

The right instrument is process isolation. Workers fall into two intrinsic categories, defined by **how they relate to the asyncio event loop**, not by what they do or which phase they belong to:

- **`shares_process` workers** (lightweight, cooperative): their per-cycle CPU stretch is short enough that the event loop can fairly multiplex them with peers. Pure DB ops, message routing, supervision queries, blackboard maintenance. They are correct citizens of a shared asyncio loop.

- **`requires_dedicated_process` workers** (heavyweight, monopolizing): they perform long synchronous CPU-bound stretches (full-codebase AST walks, graph computation) that the asyncio loop cannot fairly interleave. Hosting them with lighter peers in the same process inflates the lighter peers' cycles — and, as #519 shows, also inflates the daemon's own signal-handler latency. Network-await work (e.g. embedding via `httpx.AsyncClient` to Ollama) is *not* in this category — it releases the loop and belongs in `shares_process` even when its observed cycle gaps are large.

This split is a property of the worker's *runtime profile*, not its phase, domain, or mandate. It belongs in the worker declaration on the same constitutional footing as `schedule.max_interval` and `mandate.phase`.

### Why declarative-per-worker, not deployment-time grouping

A bare "heavy/light" split decided at deployment time is a deployment artifact — it does not survive new workers being added, it cannot be audited against governance, and it forces every operator to re-derive the classification from runtime measurement. A declarative per-worker field:

- Survives new workers (the YAML declares the truth; the runtime infrastructure picks groups from it).
- Makes the criterion debatable per worker, on the constitutional surface, not negotiated at deployment time.
- Lets the runtime fail loudly if a worker is misclassified (e.g. a `shares_process` worker observed to monopolize CPU — see D7).
- Lets future generations (multi-host, container-per-group) build on the same primitive without re-litigating the principle.

This is the same constitutional logic as ADR-041's per-worker liveness threshold: properties that vary per worker and matter for runtime behavior live on the declaration, not in operational config.

---

## Decisions

### D1 — `requires_dedicated_process` field on the worker declaration

`.intent/META/worker.schema.json` `implementation` block gains a new optional boolean property:

```json
"requires_dedicated_process": {
  "type": "boolean",
  "description": "When true, this worker must run in its own asyncio event loop (its own OS process). The lightweight daemon refuses to host it; a dedicated systemd unit runs it alone. Authority: ADR-081. Default (absent): false. Workers whose per-cycle execution includes long synchronous CPU-bound stretches (full-codebase AST walks, graph computation) must declare true — their presence in a shared loop starves peer workers' cooperative scheduling. Network-await work (e.g. embedding via httpx.AsyncClient) is NOT in this category and must declare false even when its observed cycle gaps are large — its inflation is starvation by AST-walker peers, not loop monopolization. See ADR-081 D2 for the classification criterion."
}
```

Placed on `implementation` (sibling of `requires_core_context`) because both fields govern how the daemon loader instantiates and hosts the worker, not what the worker is responsible for. Default `false` (absent = `false`) — the safer default for new workers is to share, with the drift detector (D7) catching misclassifications upward.

### D2 — Classification criterion

The perpetrator signal is **per-cycle loop-hold time**: the longest synchronous stretch a worker's coroutine holds the asyncio event loop without reaching an `await` point. Cycle-gap inflation alone is *not* a perpetrator signal — it appears on victims of starvation just as readily as on the perpetrators starving them. The #518 evidence table illustrates this directly: `blackboard_shop_manager`'s 665–1155s gaps on a 600s declared interval are *evidence of the problem this ADR solves*, not evidence that `blackboard_shop_manager` is heavy. Its per-cycle CPU work is sub-second; its inflation is contention with `audit_sensor_*` AST walkers in the shared loop.

A worker MUST declare `requires_dedicated_process: true` when **any one** of the following holds:

1. **Empirical (loop-hold)**: observed **maximum** single-stretch loop-hold time exceeds 5 seconds in any cycle over a 5+ steady-state cycle window on a clean baseline, measured by daemon-side instrumentation. Max is the gate, not p95 — starvation harm is asymmetric, dominated by the worst stretch (a worker with p95 ≈ 2s and a max of 30s once per window still wedges every peer for 30s when that stretch fires). p95 and p50 are reported alongside for tail-shape visibility but do not gate the criterion; the 5+ cycle window is the noise floor against one-off GC spikes. The instrumentation is itself a prerequisite (see D7).
2. **Categorical**: the worker performs full-codebase AST walks or graph computation as part of its per-cycle work. These are GIL-bound (pure-Python CPU) and cannot release the asyncio loop without explicit cooperative `await asyncio.sleep(0)` yield points. **Vector embedding via Ollama HTTP is *not* in this category** — embed calls go through `httpx.AsyncClient.post` in `shared.utils.embedding_utils.EmbeddingService.get_embedding`, a network await that releases the loop. The `*_embedder` workers' observed cycle inflation is starvation by AST walkers, not monopolization; they are victims, not perpetrators, and must declare `false`.
3. **Self-declared**: maintainer-asserted per-cycle CPU stretches exceeding 5 seconds on the deployment's target hardware. (Five seconds is the threshold below which event-loop starvation effects on peer workers' liveness thresholds are negligible at CORE's heartbeat-per-minute cadence.)

Cycle-gap inflation alone does NOT meet the criterion under any reading of this ADR. It is downstream of the actual signal; reading it as a perpetrator marker conflates victims with perpetrators and would propose process-isolation for workers whose per-cycle work is trivial.

Workers that satisfy none of (1)–(3) declare `false` (or omit the field). The classification is a property of the worker's *runtime profile*, not its phase or class. A sensing worker may be heavy or light; an acting worker may be heavy or light. The criterion follows the work, not the categorization.

### D3 — Runtime invariant

A worker declared `requires_dedicated_process: true` MUST run alone in its asyncio event loop — i.e., alone in its OS process. The daemon-loader infrastructure refuses to host such a worker alongside any peer (whether the peer is another `requires_dedicated_process: true` worker or any `shares_process` worker).

This is the load-bearing invariant. Two heavy workers in the same daemon still starve each other; therefore "heavy pool sharing one daemon" is not a valid relaxation of this rule. Every `requires_dedicated_process: true` worker gets its own process. (See Alternatives (b).)

The lightweight `core-daemon` process hosts every worker declared `false` (or absent). It hosts no `requires_dedicated_process: true` worker, ever. A daemon-loader that violates this invariant is a constitutional violation, surfaced by D7's drift detector.

### D4 — Daemon split shape (systemd unit topology)

The current single `core-daemon.service` unit splits into:

- **`core-daemon.service`** (unchanged name, narrowed scope): runs all `shares_process` workers in a single asyncio loop. Continues to be the unit `core-api` co-deploys with.
- **`core-daemon-worker@<stem>.service`** (new, systemd template unit): one instance per `requires_dedicated_process: true` worker, where `<stem>` is the YAML filename stem from `.intent/workers/<stem>.yaml`. `ExecStart=...core-admin daemon start --only <stem>`.

Template units are the idiomatic systemd answer for "N parameterized instances of the same service shape." `systemctl --user enable core-daemon-worker@audit_sensor_architecture.service` enables exactly that worker's dedicated daemon; the unit file is authored once and parameterized at enable time.

The singleton-PID-lock pattern from commit `f55c83f9` extends: each `core-daemon-worker@<stem>.service` uses its own PID file at `var/run/core-daemon-worker-<stem>.pid` with the same `fcntl.flock` discipline. The lock keys are per-stem; an orphan dedicated-worker daemon would surface in `core-admin daemon status`'s stray-process scan exactly as the original orphan did.

### D5 — Daemon discovery contract

`core-admin daemon start` gains a `--only <stem>` flag and an implicit `--exclude-dedicated` mode (default when `--only` is absent):

- `daemon start` (no flags): loads every active worker whose declaration has `requires_dedicated_process: false` or absent. Refuses to load any `requires_dedicated_process: true` worker; logs a one-line note per such worker explaining the skip.
- `daemon start --only <stem>`: loads exactly the worker at `.intent/workers/<stem>.yaml`. Refuses if that worker has `requires_dedicated_process: false`. Refuses if the stem does not exist or its declaration `metadata.status` is not `active`.

The two modes are mutually exclusive and explicit. There is no "load everything" mode — the single-process-all-workers shape this ADR retires must not be reachable from CLI.

`--only` is constrained to one stem per invocation, not a comma-separated list. The constitutional unit is "one heavy worker, one process"; grouping multiple stems into one process is the rejected Alternative (b).

### D6 — `core-admin daemon up/down/restart/status` wrappers

The wrappers introduced in `f55c83f9` expand from the hardcoded pair `("core-daemon", "core-api")` to a dynamically-computed unit list:

```
core-daemon
core-api
core-daemon-worker@<stem1>.service  ← one per requires_dedicated_process: true worker
core-daemon-worker@<stem2>.service
…
```

The list is derived at command time by scanning `.intent/workers/*.yaml` for `requires_dedicated_process: true` and `metadata.status == "active"`. Drift between the YAML state and the enabled systemd units (a worker flips `true` but its template unit was never enabled, or vice versa) is surfaced by `daemon status` as a third row class — "expected unit, not enabled" or "enabled unit, not in YAML."

`daemon status`'s stray-process scan (already present in `f55c83f9`) extends to recognize dedicated-worker daemons by their `--only` argument signature, so legitimate dedicated daemons are not flagged as strays.

### D7 — Drift detector audit rule

The audit rule `runtime.worker_process_classification` consumes **per-cycle loop-hold time**, not cycle-gap inflation, for the reason stated in D2: gap inflation cannot distinguish a perpetrator from its victims. Using cycle-gap data as a classification signal — the original framing of this section — would fire `escalation_required` on `blackboard_shop_manager` and other starved-but-trivial workers, proposing process-isolation for workers whose per-cycle work is sub-second. That outcome is the failure mode this revision exists to prevent.

**Prerequisite — loop-hold instrumentation.** CORE does not currently instrument per-coroutine loop-hold time. The instrumentation is a named prerequisite for D7; D7 cannot ship before it. Two paths:

- **Cheap first cut**: enable `loop.set_debug(True)` on the daemon with a tuned `slow_callback_duration` (e.g., 1.0s). Slow-callback warnings land in the journal with the callback identifier; a journal-mining query yields per-worker loop-hold incidents.
- **Production-grade**: per-coroutine sampling that records p50/p95/max loop-hold per cycle to `worker_registry` or a dedicated blackboard subject. Higher cost, lower friction at audit time.

The rule fires on:

- **`escalation_required`** — a worker declared `shares_process` (false or absent) whose observed **maximum** single-stretch loop-hold time exceeds 5s in any cycle over a 5+ steady-state cycle window. The worker is monopolizing the loop and starving peers; finding proposes flipping to `requires_dedicated_process: true`. Max is the gate per D2(1); p95 is reported alongside as advisory tail-shape but does not fire the rule on its own — a worker with a clean p95 and one bad max stretch per window is the exact case this rule must catch (its peers experience the full starvation cost of that stretch).
- **`deescalation_candidate`** (advisory only) — a worker declared `requires_dedicated_process: true` whose observed **maximum** single-stretch loop-hold time stays consistently below 1s across the same 5+ cycle window. The worker may be running cleanly *because* it has its own loop; demoting could re-introduce the contention the dedication was answering. Governor decides. Same gate-on-max logic applies: it is the worst stretch that would cost peers post-demotion.

Cycle-gap inflation is not a drift signal under any interpretation of this rule. It is left to ADR-041's territory (*liveness*: "is this worker meeting its declared cadence?"). This ADR's drift detector answers a different question (*classification*: "is this worker monopolizing the loop?"). The two signals must not be conflated.

The rule's findings are advisory, not blocking — they propose declaration edits, they do not block daemon startup. Misclassification is a governance-debt class, not a constitutional bootstrap failure.

### D8 — Migration sequencing

The change-set lands in three sealable steps. Each step's audit posture is observable independently.

1. **Schema + initial classification (governance-only, no behavior change).**
   - Add `requires_dedicated_process` to `worker.schema.json` per D1.
   - Classify the 32 existing workers per D2's criteria. The expected `true` set is anchored on the `audit_sensor_*` AST-walker cluster (categorical per D2(2)) and any other worker subsequently confirmed by D2(1) loop-hold measurement once 3a lands. The `*_embedder` workers are explicitly *not* in the `true` set per D2(2)'s embedder carve-out. The remaining workers carry `false` (or absent).
   - Authored YAMLs land green. No runtime change; the field is read by no code yet.

2. **Daemon split (deploy-time behavior change).**
   - Add `--only` flag to `core-admin daemon start` per D5.
   - Author `core-daemon-worker@.service` template unit.
   - Expand `daemon up/down/restart/status` per D6.
   - Enable one template instance per `requires_dedicated_process: true` worker.
   - The first `daemon restart` after this step lands operationally splits the daemons. Verification: #519's graceful-shutdown lag should drop to sub-second on the lightweight `core-daemon`; cycle gaps on lightweight workers should drop to within 1.05× declared (no longer starved by peers).

3. **Loop-hold instrumentation + drift detector (steady-state governance).** Splits in two:
   - **3a** — instrument per-coroutine loop-hold time. Cheap first cut: enable asyncio debug + tune `slow_callback_duration` on the daemon; mine the journal. Production-grade: per-coroutine sampling to `worker_registry` or a dedicated blackboard subject. 3a is meaningful **pre-Step-2** as well: it identifies the actual loop-monopolizers in the current single-daemon regime, which seeds Step 1's classification with empirical grounding rather than category-only assertion.
   - **3b** — author and enable `runtime.worker_process_classification` per D7. 3b is meaningful **post-Step-2**: pre-split loop-hold data is dominated by whichever worker happened to win the loop in a given window, but classification verdicts based on it remain sound (loop-hold is the perpetrator signal regardless of regime). 3b before Step 2 is allowed; the rule will fire `escalation_required` on the genuinely heavy workers and validate Step 1's classification choices against measured reality.

**Step 1 → Step 2 ordering is strict, not optional.** Step 2's `--only` flag and the daemon's exclude-dedicated default behavior read the field Step 1 adds. Pre-Step-1, both code paths have nothing to act on: `--only` would reject every stem (none have `true` yet), and exclude-dedicated would find nothing to exclude and load everything (current behavior). Step 2's CLI surface may land before Step 1 ships only if no `daemon up` is run on the new code until Step 1 has landed. **3a may land at any time** and benefits earlier work (it seeds Step 1). **3b runs after Step 1** at minimum (it consumes the field's classifications to fire findings).

---

## Consequences

- The single-daemon-for-all-workers shape that has been the operational reality since CORE's daemon arrived is retired. The lightweight `core-daemon` is no longer the only thing systemd watches; it is one of N+1 services (`core-daemon` + `core-api` + N per-heavy-worker daemons). Operators must mentally model this; the `daemon up/down/status` wrappers' expanded scope (D6) is the primary affordance for keeping this manageable.
- `max_interval` tuning becomes a per-worker discipline against per-worker reality, not against contention with other workers. Most lightweight workers that were trending toward bumped `max_interval` values under the single-daemon regime can revert to their natural cadences. #517's re-tune scope shrinks; the bumps it was contemplating for the architecturally-suspect 5 workers are largely subsumed by this ADR (those workers move to dedicated processes; their cycles measure their own work, not contention).
- #519 (graceful-shutdown lag) becomes verification of this ADR's effectiveness. Post-Step-2, lightweight `core-daemon` shutdowns should complete in sub-second; per-heavy-worker daemons may still take 10–60s on shutdown (their own AST walk has to yield), but that lag is now localized to one worker's process and does not block the rest of the system. If #519's lag persists after Step 2, the analysis was wrong and a deeper fix is needed; if it drops, the ADR's architecture is validated.
- **Heavy-daemon shutdown can still hit SIGKILL.** Process isolation localizes the asyncio-loop monopolization to one process at a time; it does not eliminate it for the offending daemon. A heavy daemon mid-AST-walk that cannot reach an `await` point within `TimeoutStopUSec=90s` gets SIGKILLed, in which case ADR-069 D8's `finally`-block claim-release does not run and the worker's held blackboard claims are orphaned. Two mitigations apply: (i) author cooperative `await asyncio.sleep(0)` yield points into the AST-walker loop body so cancellation can land between iterations — this is the primary fix and a low-cost mechanical edit, naturally co-landing with Step 2; (ii) the lease mechanism (ADR-069 D2/D6, future work) is the recovery path for the orphaned-claim case that survives (i). Until (i) lands, orphaned-claim-on-SIGKILL is accepted risk against the lease as backstop. The original framing — that this ADR "does not require touching D8" — was wrong; isolation localizes the lag but the SIGKILL→orphan path still exists for the heavy daemon.
- **Resource cost scales with N.** Each dedicated daemon boots the full app stack: its own DB connection pool, its own `CoreContext`, its own service registry warm-up. At the expected ~8 heavy workers (the `audit_sensor_*` cluster), that is 8× memory and 8× DB-connection-pool footprint against the single Postgres on `.23`. `max_connections` and the per-pool sizing in `operational_config` should be sized for this multiplication; sharing a connection pool cross-process is not supported by SQLAlchemy's async engine model. Worth measuring after Step 2 lands to confirm headroom; if `max_connections` becomes the binding constraint, per-daemon pool size is the first knob to tune.
- The constitutional surface grows by one boolean and one drift-detector rule. The runtime surface grows by one CLI flag, one systemd template unit, and N enabled instances. The mental-model surface grows materially: operators and governors must internalize the two-tier-process shape. This is the price of correctness; the alternative is continuing to tune the wrong layer indefinitely.
- Future scaling generations (multi-host deployment, container-per-worker, k8s-per-worker) inherit this ADR's primitive cleanly. A `requires_dedicated_process: true` worker is already a unit of isolation; the next generation chooses what kind of isolation. The principle ("the worker's runtime profile is declared, not deployment-negotiated") is the load-bearing decision; the systemd template unit shape (D4) is the current generation's expression of it.

---

## Alternatives considered

- **(b) "Heavy pool" — all `requires_dedicated_process: true` workers share one daemon, separate from the lightweight `core-daemon`.** Rejected: two heavy workers in one asyncio loop still starve each other. The exact pathology this ADR exists to prevent recurs at smaller scale — `audit_sensor_architecture` (1927s) and `audit_sensor_purity` (1347s) in one process would interleave their AST walks and inflate each other's cycles. The runtime invariant in D3 is "alone in its asyncio loop" precisely because the failure mode is asyncio-loop monopolization, not deployment-density.
- **(c) Per-worker `asyncio.to_thread` offload of the CPU-bound stretch.** Rejected on mechanism, not aesthetic. Pure-Python CPU is GIL-bound; `asyncio.to_thread` runs the callable on a thread, but the thread still contends for the GIL with the main thread. A CPU-bound stretch does not free the asyncio loop in any meaningful sense — the loop's coroutine still cannot resume until the GIL bounces back, which it does only at Python's evaluation-step boundaries (roughly every 100 bytecode instructions, configurable via `sys.setswitchinterval`). Only a separate process — a separate Python interpreter, hence a separate GIL — gives true parallelism for CPU-bound Python work. The mechanism that this ADR's process-isolation exploits is the GIL-per-process boundary; threading inside one process does not cross it. (Note: `to_thread` is a correct local optimization for *I/O-bound* synchronous calls — e.g. a blocking-sync HTTP library — where the GIL is released during the syscall. A `shares_process: true` worker that uses `to_thread` for I/O-bound work is fine; one that uses it for CPU-bound work is not.)
- **(d) Runtime classifier — the daemon observes cycle gaps and dynamically reassigns workers between processes.** Rejected: the same anti-pattern as the runtime-default of `files_per_cycle_max` (ADR-070 D8): properties that govern constitutional behavior are declared, not inferred. A runtime classifier hides the classification decision from the governance surface and makes it impossible to audit. D7's drift detector is the right shape — observation feeds a *proposed declaration edit*, not a runtime reassignment.
- **(e) Enum `runtime_profile: shared | dedicated | grouped:<name>` instead of boolean `requires_dedicated_process`.** Deferred, not rejected. The boolean covers every case CORE currently has — every heavy worker we have evidence for is heavy enough to merit its own process, and no two heavy workers have a sufficiently-correlated pattern that grouping them would buy anything. If a future generation produces a "medium-heavy" cluster (workers heavy enough to starve the lightweight daemon but cheap enough to share a process between themselves), the boolean can be replaced by an enum following the [[feedback_enum_subset_canonicalize_and_fail_closed]] discipline: a new entry in `.intent/META/enums.json`, a `$ref` from `worker.schema.json`, fail-closed loader. The boolean is the current YAGNI-respecting choice.
- **(f) Bound `asyncio.gather` with `wait_for` in the daemon's shutdown loop (the local fix for #519 in isolation).** Rejected as a substitute for this ADR. It would mask the shutdown-lag symptom while leaving the cycle-gap starvation untouched (#516 / #517's original problem), and it would risk skipping the ADR-069 D8 claim-release work in `Worker.start()`'s `finally`. Process isolation per this ADR fixes both symptoms at their shared root.

---

## Verification

- `.intent/META/worker.schema.json` carries `requires_dedicated_process` as an optional boolean on `implementation` per D1.
- Initial classification of the 32 existing `.intent/workers/*.yaml` files lands per D8 Step 1; spot-check via `grep -l "requires_dedicated_process: true" .intent/workers/` returns the expected heavy set (anchored on the `audit_sensor_*` AST-walker cluster per D2(2)). The `*_embedder` workers are NOT in this set and the grep must NOT match them — they are network-await workers per D2(2)'s embedder carve-out and are victims of starvation, not perpetrators of it. A grep that includes them is a misclassification under this ADR.
- `core-admin daemon start --only <stem>` rejects stems whose declaration has `requires_dedicated_process: false`; rejects stems that do not exist or are not `active`.
- `core-admin daemon start` (no flags) refuses to load any `requires_dedicated_process: true` worker; logs the skip count.
- `core-daemon-worker@<stem>.service` template unit is authored; one instance is enabled per heavy worker; each runs to a green startup (singleton lock acquired at its per-stem PID file).
- `core-admin daemon status` shows N+1 service rows (core-daemon + core-api + per-heavy-worker units) and flags any orphan dedicated-worker daemons via the stray-process scan.
- Post-Step-2 measurement window (≥ 30 min single-daemon steady state on the lightweight `core-daemon`): every `shares_process` worker's observed p50 cycle gap is within 1.05× its declared `max_interval`. #519's graceful-shutdown elapsed on the lightweight daemon drops to sub-second across 5+ restarts.
- `runtime.worker_process_classification` audit rule fires `escalation_required` for any future drift; the rule is reachable via `core-admin code audit --rule runtime.worker_process_classification`.
- `core-admin code audit` PASS after each step ships; no rule silently disabled (`Dispatch` baseline preserved per [[feedback_honesty_gated_audit]]).

---

## References

- Issue #518 — the framing motion this ADR formalizes; carries the cycle-gap evidence table and the recommendation to author this ADR.
- Issue #519 — graceful-shutdown-lag observation; same root cause (single asyncio loop starvation), parked against this ADR's outcome.
- Issue #516 / #517 — original `max_interval`-tuning thread that revealed the wrong-layer pathology. Many of #517's re-tune decisions are subsumed by this ADR's process split.
- ADR-041 — per-worker liveness thresholds. The precedent for "runtime-relevant per-worker property lives on the declaration, not in operational config." D5's data source (per-worker cycle-gap distribution) is what D7's drift detector consumes.
- ADR-069 D8 — graceful claim-release in `Worker.start()` finally. Process isolation localizes the shutdown lag but does not eliminate the SIGKILL→orphaned-claim path on the offending heavy daemon (see Consequences); the lease mechanism (ADR-069 D2/D6) is the backstop for that path until cooperative `await asyncio.sleep(0)` yield points land in the AST-walker loop body. Any future shutdown-bounding change (e.g., a `wait_for`-bounded `asyncio.gather` in the daemon shutdown loop) must still preserve D8's contract on the path it does cover.
- ADR-070 D8 — no-runtime-fallback precedent for `files_per_cycle_max`. The constitutional logic for declaring rather than inferring is shared here.
- Paper `CORE-Workers-and-Governance-Model.md` §3.1 — workers as constitutional officers; the declaration as the sole source of standing. This ADR extends what the declaration governs to include the runtime-process-isolation profile.
- Commit `f55c83f9` — singleton PID lock + `core-admin daemon up/down/restart/status` wrappers. The lock pattern extends per-stem (D4); the wrapper scope expands to the N+1 service set (D6).
- Memory [[feedback_event_loop_starvation_diagnostic]] — the diagnostic discipline this ADR encodes structurally (compare cross-worker p50; starvation signature is whole-distribution skew; fix is process isolation, not max_interval bumps).

---

## Note — 2026-06-09 — D2(2) carve-out scope correction (re #596)

D2(2)'s categorical exclusion of `*_embedder` workers from `requires_dedicated_process: true` is scoped to the embed call's network-await shape, not to embedder workers as a whole. Where an embedder has additional sync CPU stretches outside the embed call — harvest, parse, chunking, or other prologue work without `await` points — D2(1)'s empirical gate applies regardless of category. **D2(1) is load-bearing where it disagrees with D2(2)'s categorical framing.**

Empirical case: `governance_embedder` crosses D2(1)'s 5s gate on ~70% of cycles via `GovernanceClaimHarvester.harvest()` in `run()` (a sync ~400-file walk between heartbeat and the first post-heartbeat `await`). D7 fires `escalation_required` on it under its own measurements. The embed call itself is properly async per D2(2); the prologue is what trips the gate.

Whether to flip `governance_embedder` to `true` or to add cooperative yields to its harvest is a separate operational decision not foreclosed by this Note.

Per [[feedback_append_only_adr_closure_marker]]: this Note is appended-only; the body of D2(2) is unchanged so the original framing remains readable. New classifications should read D2(2) alongside this Note.
