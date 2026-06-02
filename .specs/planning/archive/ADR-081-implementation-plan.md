<!-- path: .specs/planning/ADR-081-implementation-plan.md -->

# ADR-081 implementation plan — per-worker process-isolation classification

**Author:** Claude (session 2026-06-01 — drafted under Path A execute-verb authorization, "write a complete planning into a file")
**Revisions:**
- v2 2026-06-01 — incorporates Big Brother review round 1: AST-reparse multiplication (new P6), `DaemonConfig` `.intent/` loader correction (P5 rewritten), audit blackout window (Step 2 coordination note), `set_debug` perf-tax time-boxing (Step 0), template unit `After` drop, step numbering cleanup.
- v3 2026-06-01 — incorporates Big Brother review round 2: Step 3a's coroutine-wrapper design was measuring cycle elapsed (start-to-end of `run()` including awaits), not loop-hold (synchronous stretches between awaits). Cycle-elapsed is the signal the ADR D7 explicitly forbids as classification input. Step 3a redesigned as a structured sink for asyncio's `slow_callback_duration` warnings; Step 0 is no longer time-boxed (debug-mode stays on permanently as the only low-level loop-hold source); Open call #3 collapses with Option 1 selected; dependency graph drops the "revert Step 0" node.
- v4 2026-06-01 — incorporates Big Brother review round 3: Step 3a's handle-repr regex assumes `_format_handle(handle)` surfaces the task `name=` for `Task.__step`-wrapping handles. True on current CPython via `_format_handle` returning `repr(task)`, but not an API guarantee — and if it ever returns coroutine qualname instead, all 8 audit_sensor declarations collapse to one indistinguishable repr (P3 collision). De-risked at Step 0: verification now explicitly checks whether the journal warnings distinguish the 8 audit sensors before Step 3a's design is committed. Stale "revert after measurement window" comments in Step 0's YAML snippet and the Step 3 intro line corrected.
**Status:** Plan-of-record; pending governor review before Step 0 lands
**ADR:** `.specs/decisions/ADR-081-per-worker-process-isolation-classification.md`
**Issues:** #518 (framing), #519 (graceful-shutdown lag — verification signal), #516 / #517 (the `max_interval`-tuning thread the ADR retires)
**Precedents in scope:** ADR-041 (per-worker liveness), ADR-069 D8 (graceful claim-release contract any change must preserve)

---

## Why this file exists

ADR-081 decides the destination. This plan decides the route — what lands first, what depends on what, what evidence each step must produce before the next step is sealable, what the open governor calls are, and what to verify against the live system after each step. Track it; tick its boxes; do not commit the ADR's deferred risk to memory and lose the chain.

---

## Investigation summary — what's already in place

The following machinery is already in place and needs no new construction. Each line shortens the work the ADR's D1–D8 prescribe:

- **Singleton PID-lock pattern** (`src/cli/commands/daemon.py`, commit `f55c83f9`). Already parameterized over `_PID_FILE_REL`. Extending to per-stem `var/run/core-daemon-worker-<stem>.pid` is a constant rename, not a new pattern.
- **YAML-scanning worker discovery** (`_run_daemon_locked` in `src/cli/commands/daemon.py`). Already iterates `sorted(workers_dir.glob("*.yaml"))` and reads each declaration. Adding a `requires_dedicated_process` filter is a one-line predicate.
- **`IntentRepository.list_workers()` + `load_worker()`** — the canonical access path the ADR's drift detector and `--only` flag both consume.
- **`shared.workers.schedule.load_worker_schedule_state`** already routes through `IntentRepository`. The pattern for "read every active worker's declaration field cleanly" is established.
- **Worker base class graceful-release contract** (`Worker.start()` `finally` block, ADR-069 D8). Already covers SIGTERM-via-`CancelledError` and Exception paths. Touching it is not necessary for this ADR. **It does not survive SIGKILL** — that gap is what P4 (cooperative-yield edits) addresses, in the heavy workers' run loop, not in the base class.
- **JSONSchema validator infrastructure** (`shared.workers.declaration_validator`). Adds a boolean property to `worker.schema.json` with no validator-builder changes; tests call `reset_worker_validator_cache()`.
- **`PartOf=core-daemon.service`** on `core-api.service` — the sibling-cascade we already know about, the model the new template units have to decide whether to follow.
- **`EmbeddingService.get_embedding`** (`src/shared/utils/embedding_utils.py:122`) uses `httpx.AsyncClient.post` — a network await that releases the loop. The ADR's embedder carve-out (D2(2)) is structurally correct: `governance_embedder` and `repo_embedder` are starvation victims, not perpetrators.

---

## Hard prerequisites

### P1 — Loop-hold instrumentation does not exist anywhere
`grep -rn "set_debug\|slow_callback" src/` returns nothing. D7's drift detector and D2's empirical criterion both depend on per-coroutine loop-hold measurement that the daemon does not currently produce. The ADR (D8 Step 3a) flags this — Step 3a may land at any time but Step 3b cannot ship before it. **Without 3a, Step 1's initial classification is category-only assertion and Step 3b is unbuildable.** Cheapest viable form: enable `loop.set_debug(True)` and tune `slow_callback_duration` in `_run_daemon_locked` (one-line change plus a config-knob field). Production-grade per-coroutine sampling to `worker_registry` or a blackboard subject is a bigger lift; can defer.

This prerequisite is brought forward in the plan as **Step 0** because it is the gate. Without Step 0, the ADR's empirical claims are unverifiable and Step 1's classification choices are unauditable against measured reality.

### P2 — Initial heavy-set classification needs evidence, not vibes
Step 1 classifies the 32 workers. The ADR anchors the heavy set on the `audit_sensor_*` cluster (8 workers) per D2(2)'s categorical criterion. But D2(2) says "full-codebase AST walks or graph computation" — the implementation must be confirmed by reading `src/will/workers/audit_violation_sensor.py` (the single Python class behind all 8 declarations — see P3). An `audit_sensor_*` worker that turns out to be DB-table-driven rather than AST-walking would be a misclassification under D2 and must declare `false`. **Step 0's instrumentation produces the evidence this prerequisite asks for**; the Step 1 YAML edits read it.

### P3 — The 8 `audit_sensor_*` YAMLs share a single Python class
`grep -l AuditSensor src/will/workers/` returns one file: `audit_violation_sensor.py`. All 8 declarations bind to `will.workers.audit_violation_sensor.AuditViolationSensor` with distinct `rule_namespace` params (`architecture`, `cli`, `layout`, `linkage`, `logic`, `modularity`, `purity`, `style`). This is structurally fine for ADR-081 — isolation is per-declaration, not per-class — but means the daemon will boot 8 dedicated processes each importing the same module.

**Resource cost (Consequences §3 — "8× memory, 8× DB-connection-pool footprint") is real and concentrated here.** The Postgres at `.23`'s `max_connections` and per-daemon pool sizing in `operational_config` must be sized before Step 2c enables the template instances. SQLAlchemy's async engine cannot share a pool cross-process, so the only knob is per-daemon pool size.

### P6 — 8 dedicated processes = 8 concurrent full-codebase AST re-parses (Big Brother review)

`AuditViolationSensor.run()` at `src/will/workers/audit_violation_sensor.py:122-124` calls `auditor_context.reload_governance()` and `auditor_context.invalidate_file_cache()` every cycle. In the **shared-process world today**, all 8 sensor declarations hold a reference to the single `self._core_context.auditor_context` (the service-registry singleton); their cycles serialize on the event loop, and each parse benefits from any per-cycle caching that survives `invalidate_file_cache`'s reset point. In the **8-dedicated-process world** prescribed by Step 2c, each daemon process constructs its own `CoreContext` → its own `auditor_context` → its own file cache, with no cross-process sharing possible.

The consequence: 8 dedicated processes can — and on a 1200s cadence likely will — run full-codebase AST walks **simultaneously** rather than serially. The work shape "parse the whole repo, evaluate 8 different rule sets against it" decomposes structurally into `1× parse + 8× rule-evaluation`. The per-namespace-process split forces it into `8× parse + 8× rule-evaluation` — an 8× throughput regression on the parse half and a probable core-saturation event on the lira host that the ADR's Consequences section did not anticipate. The starvation fix exists; the throughput problem it introduces is a new failure mode.

This is **the gate question for Step 2c.** Two paths forward:

- **Path A — consolidate before split.** Author a sibling ADR (call it ADR-082 placeholder) that consolidates `AuditViolationSensor` into a single walker that parses once and dispatches results to N rule-namespace evaluators. The consolidated worker is the `requires_dedicated_process: true` unit; the 8 YAMLs collapse to one declaration (or remain as namespace-config declarations but bind to a different runtime topology — to-design). Step 2c then enables ONE template instance, not 8.
- **Path B — accept 8× re-parse as the cost of isolation.** Land Step 2c as planned, measure the throughput hit and CPU saturation on lira under steady state, decide post-hoc whether the impact is tolerable. Cheap to execute, real risk of "now I have 8 processes pegging cores" being a worse operational reality than starvation was.

**Path A is the correct shape per Big Brother's reading**, and per the ADR-018 decomposed-crawler/embedder precedent the codebase already follows for the `repo_embedder` cluster. But Path A is a sibling ADR plus a non-trivial refactor of `AuditViolationSensor` (the `reload_governance` + `invalidate_file_cache` semantics + the per-namespace dedup contract have to compose cleanly under a single-walker shape), and must not be tacked onto this plan without its own design pass. **Recommendation: raise the consolidation question as a sibling ADR BEFORE Step 2c. Steps 0, 1, 2a, and 2b are not blocked by it** — they produce evidence and surface CLI/cooperative-yield mechanics that the consolidation work would build on. The choice point is Step 2c.

**Verification before deciding Path A vs B (Step 0 + targeted measurement):**
- Under Step 0's instrumentation, log per-cycle elapsed time of `auditor_context.reload_governance()` + the rule-evaluation half. The ratio of `parse:evaluate` per cycle, multiplied by 8, is the throughput-regression magnitude.
- Spot-check whether `auditor_context.invalidate_file_cache()` leaves any in-memory state that the next `reload_governance` benefits from (cross-cycle caching). If yes, the per-process-isolation cost is higher still (each new process pays cold-cache cost on every cycle); if no, the cross-cycle baseline is already cold and the regression is bounded by within-cycle re-parse.
- Read `auditor_context` construction to confirm whether two `CoreContext` instances would in fact each instantiate their own `auditor_context` (singleton-per-context) or whether there's a process-global shortcut. (The latter would change the analysis substantially; I have not verified it for this plan.)

### P4 — Heavy-worker cooperative-yield edit is not optional
ADR Consequences paragraph 4 retracts the ADR's earlier "does not require touching D8" framing: heavy daemons mid-AST-walk that cannot reach an `await` between SIGTERM and systemd's `TimeoutStopUSec=90s` still get SIGKILLed, which bypasses Worker.start()'s `finally` block, which orphans any held claims. The mitigation — `await asyncio.sleep(0)` between AST-walker iterations — is named as the primary fix and "naturally co-lands with Step 2." **Treat this as part of Step 2, not deferred.** Without it, Step 2 trades the broad symptom (all-worker starvation) for a localized symptom (orphaned claims on heavy-daemon SIGKILL).

### P5 — Operational-config touches are `.intent/`-governed, not just code (corrected per Big Brother)

The original framing of this prerequisite — that `@dataclass(frozen=True)` was a barrier to extending `DaemonConfig` — was wrong. `frozen=True` blocks **instance attribute mutation after construction**; it does not block adding fields to the class definition. The real prerequisite is that `DaemonConfig` is loaded from `.intent/enforcement/config/operational_config.yaml` via `_load_daemon` at `src/shared/infrastructure/intent/operational_config.py:674`. Adding a `slow_callback_duration_sec` field (for Step 0) or a `WorkerClassificationConfig` block (for Step 3b) is **a governance edit**, not a pure-code edit:

- New field on the `@dataclass(frozen=True) DaemonConfig` in `operational_config.py` (code).
- New line in the `daemon:` section of `.intent/enforcement/config/operational_config.yaml` (governance).
- New `_get_*` call inside `_load_daemon` reading the YAML key (code).

The `.intent/enforcement/config/` subtree is permissive territory under CLAUDE.md's confirmation gate (it's not `.intent/META/` or `.intent/constitution/` — no heightened confirmation needed), but it is governance, and **Step 0 must carry an explicit Path A confirmation for the YAML edit** the same as Step 1's schema edit does. The plan's earlier "Step 0 has no `.intent/` touch" gate was incorrect on this point.

---

## Open governor calls before Step 0

These are decisions I cannot make on the ADR's authority alone. Resolve before Step 2c at latest; ideally before Step 0 so they don't pile up.

1. **Postgres pool sizing for the per-stem multiplication (P3).** Confirm `max_connections` headroom on the Postgres at `.23` for ~10 daemons (`core-daemon` + `core-api` + 8 `core-daemon-worker@audit_sensor_*`). If headroom is tight, per-daemon pool sizing in `operational_config` is the first knob.
2. **`PartOf` cascade decision for the template unit (D4).** Default I'd recommend: **independent units** (no `PartOf=core-daemon.service`). Failure-domain isolation matches the constitutional principle "one heavy worker, one process, one failure domain"; the `daemon up/down/restart` wrappers per D6 still drive coordinated lifecycle from a single command. The opposite call ("`PartOf` for operational convenience") would make a heavy worker crash cascade into the rest. Governor decides.
3. **Step 0 telemetry lifetime — resolved v3, Option 1 selected.** The v2 framing offered a measurement-window vs permanent fork. v2 was unsound: BB's round-2 review (2026-06-01) established that loop-hold (the metric D7 requires) is only observable at the event-loop's per-`Handle` boundary, which `loop._run_once` checks against `slow_callback_duration` only when `_debug=True`. A wrapper outside the coroutine measures cycle-elapsed (start-to-end of `run()`, including awaits) — the cycle-gap-shaped signal the ADR D7 explicitly forbids. Three real options exist:

   - **Option 1 (selected) — keep debug-mode on permanently; structure the output.** Step 0's `set_debug(True)` + `slow_callback_duration` stays on forever. Step 3a-telemetry adds a `logging.Handler` (or filter) on the `asyncio` logger that intercepts the slow-callback warning records, extracts the handle + duration, and posts them as `loop_hold.sample` blackboard entries. Accepts standing debug overhead (coroutine-origin tracking, "task never awaited" detection, per-handle timing) as the cost of structured loop-hold telemetry. Pragmatic; smallest engineering surface; Step 3b-rule reads structured data.
   - **Option 2 — custom event-loop subclass.** Override `BaseEventLoop._run_once`'s timing path to emit structured samples without `_debug=True`'s other overheads. Technically cleanest (no standing debug tax), but creates ongoing maintenance burden against CPython internals — `_run_once`'s shape changes between minor versions, and the asyncio team does not guarantee subclass stability. Significant engineering lift for a perf gain we have not measured to be necessary.
   - **Option 3 — accept debug-on permanently; drop Step 3b's machine-readable goal.** Step 0 stays on; Step 3b is a journal-mining tool (grep against text) rather than a blackboard-data rule. Fragile against log-format changes; not auditable via `core-admin code audit --rule …`. Not recommended.

   **Selected: Option 1.** Surfaced explicitly so the governor may override toward Option 2 if the standing debug overhead measures to be unacceptable under Step 0's window. Open call collapses to "confirm Option 1 before authoring Step 3a-telemetry's handler implementation."
4. **Consolidation vs 8-way split for the `audit_sensor_*` cluster (P6, Big Brother concern #1).** This is the gate decision for Step 2c. Path A (consolidate to one walker via sibling ADR, then enable one template instance) vs Path B (accept 8× re-parse and measure). Governor decides; Steps 0/1/2a/2b are not blocked by this call, but Step 2c MUST NOT land until it's resolved. If Path A: the consolidation ADR is its own design pass and adds calendar time; if Path B: explicit acceptance of the throughput regression should be recorded in this plan and in the ADR's Consequences section.

---

## Step plan

The ADR's D8 prescribes three sealable steps. This plan adds **Step 0** (P1's instrumentation, brought forward) and decomposes Step 2 into three sub-steps so each is operationally reversible. Each step's audit posture is observable independently per [[feedback_honesty_gated_audit]] — snapshot `core-admin code audit`'s `Dispatch: M·N` line before/after to confirm no rule silently disabled.

---

### Step 0 — Loop-hold instrumentation (permanent telemetry source, Option 1)

**Goal:** make the asyncio event loop's per-handle synchronous-stretch timing observable, so the `audit_sensor_*` cluster's loop-hold reality can be measured before Step 1's YAML edits make classification claims about it AND so Step 3a-telemetry can wire its output into a structured sink. **Per Open call #3 (Option 1 selected), Step 0 is permanent infrastructure, not a measurement window.** The debug-mode tax is the cost of the only low-level loop-hold source CPython provides.

**Lands in:**
- `.intent/enforcement/config/operational_config.yaml` — add to the `daemon:` section:
  ```yaml
  daemon:
    one_shot_interval_sec: 300
    slow_callback_duration_sec: 1.0  # ADR-081 Step 0; permanent per Option 1
    set_debug: true                   # ADR-081 Step 0; permanent per Option 1
  ```
- `src/shared/infrastructure/intent/operational_config.py` — add `slow_callback_duration_sec: float = 0.1` and `set_debug: bool = False` fields to `DaemonConfig`; read them in `_load_daemon` via `_get_float` / `_get_bool`. Defaults are the **off** state so reverting the YAML returns to clean baseline.
- `src/cli/commands/daemon.py:_run_daemon_locked` — before the worker-task-loop, add:
  ```python
  loop = asyncio.get_running_loop()
  if _CFG.set_debug:
      loop.set_debug(True)
      loop.slow_callback_duration = _CFG.slow_callback_duration_sec
  ```
  (The existing `loop = asyncio.get_running_loop()` assignment further down moves up; the call to `loop.add_signal_handler(...)` already there continues to work.)

**Constitutional gates:**
- Step 0 IS a governance edit per P5 (corrected): the `.intent/enforcement/config/operational_config.yaml` change requires explicit Path A confirmation in the turn it lands. Not Path B — the value choices (1.0s threshold, debug on) are semantic.
- The code-side fallback defaults are **off** so a future YAML revert cleanly returns to no instrumentation.
- No worker schema touch (`worker.schema.json` is not modified — that's Step 1).
- No new audit rule.

**Verification:**
- `core-admin daemon restart` (the wrapper from `f55c83f9`).
- 30 minutes of steady-state observation.
- `journalctl --user -u core-daemon | grep -i "slow\|Executing"` shows entries naming the `audit_sensor_*` cluster.
- `core-admin code audit` PASS; `Dispatch: M·N` unchanged.
- **Attribution check (gates Step 3a's design — Big Brother round-3 review).** All 8 `audit_sensor_*` declarations bind to the same `AuditViolationSensor.run` coroutine (P3); their qualnames are identical. Step 3a's regex extracts the worker stem from the slow-callback warning's handle repr, which on current CPython surfaces `repr(task)` for `Task.__step`-wrapping handles — and `repr(task)` carries `name='<stem>_worker'` because the daemon names tasks via `asyncio.create_task(coro, name=...)` at `daemon.py:542`. But this is implementation detail, not API: if `_format_handle` ever returns the coroutine qualname instead, all 8 sensors collapse to one indistinguishable `<coroutine AuditViolationSensor.run …>` repr and per-namespace attribution dies.
  - **Check:** `journalctl --user -u core-daemon | grep "Executing.*took.*seconds"` over the 30-min window must show ≥2 distinct task names from the `audit_sensor_*` cluster (e.g., both `audit_sensor_architecture_worker` and `audit_sensor_purity_worker` appearing in different warning lines).
  - **If the check passes** (current CPython behavior holds): Step 3a's regex approach is sound; proceed as designed.
  - **If the check fails** (warnings show only coroutine qualname or no name distinguisher): Step 3a's `logging.Handler` regex is dead on arrival. Mitigation requires task-name injection independent of `_format_handle` — either a custom `loop.set_task_factory` setting the name explicitly via `contextvars` carried through to handler emission time, or storing the worker UUID in a contextvar that the handler reads. Either is a bigger lift than 3a's current design; surfacing the need at Step 0 means it's planned, not discovered.
  - Outcome of this check feeds Open call #3's confirmation (Option 1 viable as designed vs Option 1 needs contextvars upgrade vs Option 2 becomes more attractive).

**Output that downstream steps consume:**
- A confirmed list of which workers actually monopolize the loop and for how long. Feeds Step 1's classification (which YAMLs flip to `true`).
- Measurement evidence for the P6 consolidation-vs-split call (parse-half vs evaluate-half elapsed within `AuditViolationSensor`).
- **The journal warning stream is the raw source Step 3a-telemetry's handler subscribes to.** Step 0's `loop.set_debug(True)` is not reverted post-Step-3a; the handler reads from the same emission path Step 0 turned on.

**Reversibility — for emergency rollback only, not the steady-state plan:**
- Set `daemon.set_debug: false` and `daemon.slow_callback_duration_sec: 0.1` (default) in the YAML.
- Restart daemon. `set_debug(True)` is dropped because the gate in `_run_daemon_locked` evaluates the new config and skips the enablement; the loop returns to non-debug mode.
- Step 3a-telemetry's handler then receives no records; Step 3b-rule has no data; the drift detector goes silent. Use only if standing debug overhead is measured to be unacceptable and the governor chooses to abandon Option 1 in favor of Option 2 (custom event loop) or Option 3 (drop machine-readable rule).

---

### Step 1 — Schema + initial classification

**Goal:** add the `requires_dedicated_process` field to the worker schema and classify the 32 existing declarations per D2's criteria, evidenced by Step 0's instrumentation output. No runtime behavior change — the field is read by nothing yet.

**Lands in:**
- `.intent/META/worker.schema.json` — add to the `implementation` block:
  ```json
  "requires_dedicated_process": {
    "type": "boolean",
    "description": "<verbatim from ADR-081 D1>"
  }
  ```
  Place as sibling of `requires_core_context`. No `additionalProperties: true` change (schema already accepts unknown-listed properties; adding one is additive).
- `.intent/workers/audit_sensor_architecture.yaml` and the 7 sibling `audit_sensor_*` files — add `requires_dedicated_process: true` under `implementation`. Subject to Step-0 evidence per P2: any of the 8 that Step-0 shows is *not* loop-monopolizing must NOT receive the field (declare false / omit).
- Every other `.intent/workers/*.yaml` (24 files): no change. Absent = `false` is the safer default per D1.
- The `*_embedder` carve-out per D2(2): `governance_embedder.yaml` and `repo_embedder.yaml` MUST NOT receive `true`. The ADR's Verification spot-check is `grep -l "requires_dedicated_process: true" .intent/workers/` must not match `*embedder*`.

**Constitutional gates:**
- `.intent/META/` and `.intent/workers/` are governance surfaces. Per CLAUDE.md, schema and worker-declaration edits land under Path A in the turn the governor explicitly authorizes them. **Step 1 must be a single turn with explicit confirmation per file.** Path B (mechanical substitution) does not apply — the field-add and the classification choices are semantic.
- `reset_worker_validator_cache()` in any test that touches the schema in-process. The runtime validator is `@cache`-d via `_VALIDATOR_CACHE`; daemon restart picks up the new schema cleanly.

**Verification:**
- `core-admin code audit` PASS; `Dispatch: M·N` unchanged (the new field is additive; no rule disables).
- All 32 worker declarations validate (`python -c "from shared.workers.declaration_validator import get_worker_validator; get_worker_validator()"` — succeeds).
- Spot-check grep: `grep -l "requires_dedicated_process: true" .intent/workers/` returns exactly the 8 (or fewer per P2) audit_sensor files; does NOT return any `*embedder*` file.
- Daemon restart: every worker still loads (no schema validation failure).

**Output that downstream steps consume:**
- A schema field that Step 2a's `--only` flag and Step 2c's `daemon status` enumeration can read.

**Reversibility:** revert the YAML edits and the schema edit. No runtime state to migrate.

---

### Step 2 — Daemon split

**Operational coordination note (Big Brother concern #2 — audit blackout).**
Once Step 2a's exclude-dedicated default lands and `core-daemon` restarts, the heavy workers (`audit_sensor_*`) run nowhere until Step 2c's template instances are enabled. That's an audit-sensing blackout for the architecture, purity, cli, layout, linkage, logic, modularity, and style namespaces for the duration of the gap. **Do not run an operational `daemon restart` between 2a and 2c.** Two acceptable shapes:

- **2a+2b+2c land as one coordinated change-set with a single operational restart.** Code and YAMLs land in separate commits for diff hygiene, but the systemctl-touching restart happens once, at the bottom of 2c. This is the recommended path.
- **Bridge with foreground `core-admin daemon start --only <stem>` runs.** If 2a/2b ship and a restart happens before 2c, manually start each heavy sensor in a foreground shell to cover the gap. Operationally fragile (foreground processes don't survive shell exit) — only acceptable if 2c is hours away, not days.

The plan's earlier sub-step decomposition was about code-review reversibility, not operational independence; the systemctl-touching restart in 2c is the single operational checkpoint.

---

**2a — `--only <stem>` flag and exclude-dedicated default (no systemd change yet)**

**Goal:** teach `core-admin daemon start` to load exactly one heavy worker or exclude all heavy workers, without yet changing what systemd runs.

**Lands in:**
- `src/cli/commands/daemon.py`:
  - Add `--only <stem>` typer option to the `start` command.
  - Per D5: with `--only`, load exactly `.intent/workers/<stem>.yaml`, refuse if `requires_dedicated_process: false`, refuse if non-`active`. Without `--only`, exclude every worker with `requires_dedicated_process: true` and log an `info`-level skip note per such worker.
  - The two modes are mutually exclusive. No "load everything" mode.
  - Singleton-lock parameterized per-stem: when `--only <stem>` is passed, the PID file is `var/run/core-daemon-worker-<stem>.pid`. The lightweight daemon retains `var/run/core-daemon.pid`. This means an operator can run `core-admin daemon start` and `core-admin daemon start --only audit_sensor_architecture` simultaneously and they won't fight for the same lock.

**Constitutional gates:**
- Pure CLI surface change. No `.intent/` touch, no systemd touch.
- The new `--only` mode is reachable but no production systemd unit invokes it yet. Safe to land independently.

**Verification:**
- `core-admin daemon start --only audit_sensor_architecture` (run manually in a foreground shell) starts only that worker; check `core-admin daemon status`'s stray-process scan flags it correctly until 2c enables a unit (it will appear as a stray under 2a — this is expected, this is why 2c lands after 2a).
- `core-admin daemon start --only blackboard_shop_manager` (a lightweight worker) is refused with a clear error.
- `core-admin daemon start --only nonexistent_worker` is refused.
- `core-admin daemon start` (no flag) starts only the workers NOT marked `requires_dedicated_process: true` — verify via `journalctl --user -u core-daemon | grep "started worker"` count matches 32 − heavy-set-size.
- `core-admin code audit` PASS.

**Output:** a CLI surface that 2c's systemd template unit will invoke.

**Reversibility:** revert daemon.py; restart the lightweight daemon.

---

**2b — Cooperative-yield edits in `AuditViolationSensor` (P4)**

**Goal:** add `await asyncio.sleep(0)` yield points to the AST-walker loop body so the heavy worker can reach a cancellation point within systemd's `TimeoutStopUSec=90s` and Worker.start()'s `finally` actually runs on SIGTERM.

**Lands in:**
- `src/will/workers/audit_violation_sensor.py` — identify the file-iteration loop in the AST walker. Add `await asyncio.sleep(0)` between file iterations (or every N files if per-file yield is excessive overhead — measure under Step 0 instrumentation).
- Any other worker that Step 0 surfaces as a loop-monopolizer beyond the audit_sensor cluster.

**Constitutional gates:**
- Worker base class is NOT touched. ADR-069 D8's contract is preserved unchanged.
- The edit is a behavior-shaping change in the heavy worker's run body, not a base-class concern.

**Verification:**
- Restart daemon with Step 0 instrumentation active.
- `core-admin daemon stop` (via wrapper) on the heavy worker (once 2c lands; until then, send SIGTERM manually).
- Confirm `journalctl` shows Worker base class's "released N held claim(s) at shutdown (ADR-069 D8)" log line, indicating the `finally` block ran.
- Confirm shutdown elapsed time < `TimeoutStopUSec=90s` (no SIGKILL escalation).
- Pre-2c, this is tested by running `core-admin daemon start --only audit_sensor_architecture` in a foreground shell and Ctrl-C'ing it.

**Output:** SIGKILL-on-shutdown risk localized to "AST walk overruns 90s with no yield" — a genuine bug to fix, not an architectural inevitability.

**Reversibility:** revert the sleep-zero insertions.

---

**2c — Systemd template unit + `daemon up/down/restart/status` expansion**

**Goal:** make systemd run the split deployment shape ADR D4 prescribes. This is the irreversible-feeling step (touches the user-systemd config); reversibility section below covers the rollback.

**Lands in:**
- `/home/lira/.config/systemd/user/core-daemon-worker@.service` — new template unit. Shape:
  ```ini
  [Unit]
  Description=CORE Background Worker Daemon — dedicated for %i
  After=network.target
  # Note: `postgresql.service` is intentionally NOT listed in After=.
  # Postgres runs on a remote host (.23); there is no local unit to order
  # against. Per Big Brother review 2026-06-01.
  # PartOf decision pending governor: see Open Governor Calls #2.

  [Service]
  Type=simple
  WorkingDirectory=/opt/dev/CORE
  Environment="PATH=/opt/dev/CORE/.venv/bin:/home/lira/.local/bin:/usr/local/bin:/usr/bin:/bin"
  Environment="VIRTUAL_ENV=/opt/dev/CORE/.venv"
  ExecStart=/opt/dev/CORE/.venv/bin/core-admin daemon start --only %i
  Restart=on-failure
  RestartSec=10
  StandardOutput=journal
  StandardError=journal
  SyslogIdentifier=core-daemon-worker-%i

  [Install]
  WantedBy=default.target
  ```
- `systemctl --user enable core-daemon-worker@audit_sensor_architecture.service` (×8 for the heavy set).
- `src/cli/commands/daemon.py`:
  - Replace `_SYSTEMD_UNITS = ("core-daemon", "core-api")` with a function that scans `.intent/workers/` and returns the dynamic list.
  - `_systemctl(verb)` accepts the dynamic list.
  - `status` command:
    - Iterates the dynamic list; renders N+1 rows.
    - Stray-process scan: legitimate dedicated daemons are recognized by their `core-admin daemon start --only <stem>` cmd signature OR by their PID being in the enabled-units' MainPID set. Either filter is sufficient.
    - New row class per D6 — "expected unit, not enabled" or "enabled unit, not in YAML" — surfaces drift between YAML state and systemd state.

**Constitutional gates:**
- The template unit file lives outside the repo (in `~/.config/systemd/user/`). Per CLAUDE.md, files outside `src/`, `tests/`, `.intent/`, `.specs/`, `var/prompts/` are not Claude's territory. **The governor authors the template unit file directly**; this plan provides the content above for paste. The repo-side daemon.py changes are Claude's territory and land in the same step.

**Verification:**
- `core-admin daemon status` shows 10 rows (lightweight `core-daemon` + `core-api` + 8 `core-daemon-worker@audit_sensor_*`), no strays.
- `core-admin daemon restart` (via wrapper) cycles all 10 units; each comes back active.
- `#519`'s graceful-shutdown lag on the lightweight `core-daemon` drops to sub-second across 5+ `daemon restart` invocations (≥30 min interleaved steady-state observation).
- Every `shares_process` worker's observed p50 cycle gap drops to within 1.05× declared `max_interval` (specifically: `blackboard_shop_manager` at 600s declared should observe p50 ≤ 630s, not the 665–1155s the ADR's evidence table cited).
- DB connection-pool sanity: `SELECT count(*) FROM pg_stat_activity WHERE usename = 'core'` under steady state confirms ~10 daemons' pool sum stays within `max_connections`. If tight, tune per-daemon pool size via `operational_config`.
- `core-admin code audit` PASS.

**Output:** the deployment shape the ADR specifies, in steady state, with the verification signal that distinguishes "ADR correctly diagnosed" (#519 drops) from "diagnosis was wrong" (#519 persists).

**Reversibility:**
- `systemctl --user disable core-daemon-worker@audit_sensor_*.service` (×8).
- `systemctl --user stop core-daemon-worker@audit_sensor_*.service` (×8).
- Revert daemon.py to use the static `_SYSTEMD_UNITS` constant.
- Revert Step 1's YAML edits (the heavy workers go back to the lightweight `core-daemon`).
- Leave Step 2b's cooperative-yield edits in place (they're benign in a shared-loop regime — the yield-zero is a no-op if no other coroutine is ready).

---

### Step 3 — Drift detector audit rule (`runtime.worker_process_classification`)

Split into two sub-steps to separate the telemetry source from the rule that consumes it. Step 3a-telemetry adds a structured sink (`logging.Handler` → `loop_hold.sample` blackboard subject) on top of Step 0's permanent debug-mode instrumentation; Step 3b-rule lands the audit rule that mines it. Step 3a is additive to Step 0 — it subscribes to Step 0's emission path, does not replace it.

**3a-telemetry — structured sink for slow-callback warnings (Option 1).**

**Goal:** make Step 0's asyncio slow-callback signal machine-readable so Step 3b-rule consumes structured data, not journal text. **Does NOT replace Step 0** — Step 0's `loop.set_debug(True)` + `slow_callback_duration` is the only source of loop-hold timing in CPython's stdlib; Step 3a only restructures its output channel.

**Why this design and not a coroutine wrapper.** A `time.monotonic()` wrapper around the worker's `run()` coroutine measures elapsed time from coroutine-start to coroutine-end, which includes every `await` (sleeps, DB waits, HTTP waits). That's cycle elapsed — the cycle-gap-shaped signal ADR-081 D7 explicitly forbids as classification input. Loop-hold (the synchronous stretch between two awaits) is only observable at the event loop's per-`Handle` boundary, where `_run_once` measures handle execution time against `slow_callback_duration` and emits a `logger.warning` when `_debug=True`. The handler below subscribes to that emission path.

**Lands in:**
- `src/cli/commands/daemon.py:_run_daemon_locked` — after the `set_debug(True)` block from Step 0, install a `logging.Handler` on the `asyncio` logger:
  ```python
  import logging, re
  asyncio_logger = logging.getLogger("asyncio")
  asyncio_logger.addHandler(_SlowCallbackBlackboardHandler(ctx))
  ```
- New module (or addition to `src/shared/workers/`) — `_SlowCallbackBlackboardHandler(logging.Handler)`:
  - In `emit(record)`, filter for the slow-callback signature: `record.args` is a 2-tuple `(handle_repr, duration_seconds)`, message format `"Executing %s took %.3f seconds"`.
  - Extract worker stem from `handle_repr` via regex on `name='<stem>_worker'` — daemon code already names tasks distinctively per `asyncio.create_task(coro, name=f"{stem}_worker")` at `daemon.py:542`.
  - Post a `loop_hold.sample` blackboard entry under that worker's UUID with payload `{"duration_sec": <duration>, "handle": <handle_repr>, "ts": <iso>}`.
  - Handler must be defensive: malformed records (no args, unparseable handle), missing worker UUID lookup, or blackboard-write failure must not propagate — slow-callback emission is on the asyncio hot path and a handler exception would inject latency back into the loop.
  - Handler MUST NOT use synchronous DB writes from inside `emit()` — it would block the loop it's measuring. Use `asyncio.create_task(...)` to schedule the blackboard post, or buffer to an `asyncio.Queue` drained by a dedicated coroutine.

**Verification:**
- `loop_hold.sample` blackboard entries appear with each slow-callback emission, carrying duration consistent with the journal warning's text.
- Handler exception path verified — install a malformed-args test record, confirm no crash.
- Loop-back check: handler's own emission cost does not itself trigger slow-callback warnings (verify under Step 0 instrumentation; if it does, the queue-drained pattern is mandatory not optional).
- `core-admin code audit` PASS; `Dispatch: M·N` unchanged (no new rule yet).

**What 3a does NOT do:**
- Does not revert Step 0's `set_debug(True)`. Step 0 stays on.
- Does not compute p50/p95/max — those are derived at rule-evaluation time by Step 3b, querying the `loop_hold.sample` entries over the 5-cycle window.
- Does not measure cycle elapsed. That signal is forbidden by ADR D7.

---

**3b-rule — the `runtime.worker_process_classification` audit rule.**

**Goal:** make the classification claim machine-checkable. Workers that observably monopolize the loop but declare `shares_process` fire `escalation_required`; workers that observably stay quiet but declare `requires_dedicated_process` fire `deescalation_candidate` (advisory only).

**Lands in:**
- New `.intent/enforcement/mappings/runtime/` directory (does not currently exist; `ls .intent/enforcement/mappings/` shows `architecture/`, `code/`, `ai/`, `cli/`, `coherence/`, `data/`, `governance/`, `infrastructure/`, `will/` — none `runtime/`).
- `.intent/enforcement/mappings/runtime/worker_process_classification.yaml` — the rule mapping (`rule_id: runtime.worker_process_classification`, check_type, scope).
- An engine implementation. The check_type and engine convention need to agree per [[feedback_three_layer_intent_alignment]]; this rule's verdict is data-driven (consumes 3a-telemetry's `loop_hold.sample` blackboard entries), not AST-driven, so it likely lives in a new engine module under `src/mind/logic/engines/` consistent with existing data-driven engines. Pattern to research before drafting.
- `src/shared/infrastructure/intent/operational_config.py` + `.intent/enforcement/config/operational_config.yaml` — add `WorkerClassificationConfig` dataclass (per P5) with `loop_hold_escalation_sec: float = 5.0`, `loop_hold_deescalation_sec: float = 1.0`, `cycle_window: int = 5`. These are the gates D7 spells out, governed via the standard operational-config path.

**Constitutional gates:**
- D7's findings are advisory, not blocking. The rule's verdict is a proposed declaration edit, not a daemon-startup gate.
- D7 consumes loop-hold data, NOT cycle-gap data. Conflating them re-introduces the failure mode the ADR exists to prevent ([[feedback_event_loop_starvation_diagnostic]]).
- Per [[feedback_count_from_source_not_narrative]], the 5s / 1s / 5-cycle gates above are quoted from the ADR's D2(1) and D7 — verify against the ADR text before authoring.

**Verification:**
- Rule reachable: `core-admin code audit --rule runtime.worker_process_classification` runs without error.
- Expected post-Step-2 output: clean PASS (the classification baked in at Step 1 should match measured reality once heavy workers are isolated).
- Synthetic test: temporarily flip `audit_sensor_architecture`'s declaration to `false` and re-run; rule fires `escalation_required`. Revert.
- `Dispatch: M·N` increments by 1 (one new rule). Confirm.

**Output:** the audit-pipeline closed loop. Future drift (a new heavy worker that's misclassified, an existing heavy worker that becomes cheaper and could de-escalate) surfaces as a finding.

**Reversibility:** delete the mapping and engine. The rule disappears from the audit run.

---

## Cross-cutting verification discipline

Per the memories indexed in `MEMORY.md`:

- **[[feedback_honesty_gated_audit]]** — after every step, snapshot `core-admin code audit`'s `Dispatch: M·N` line; confirm the count is monotone-non-decreasing where it should be (Step 3 adds one rule) and unchanged elsewhere. The Step-1 schema edit specifically must NOT silently disable any rule.
- **[[reference_audit_dispatch_line_restart_tell]]** — after each daemon restart, verify the new code is loaded by reading the `Dispatch:` line; a stale `core-api` means the audit is meaningless.
- **[[feedback_engine_context_dispatch_needs_verify_context]]** — when Step 3's new engine lands, confirm it has `verify_context` not just `verify` if it's context-level.
- **[[feedback_orphan_daemon_pretest]]** — before each step's verification window, run `ps -ef | grep core-admin` to confirm no orphan daemon contaminates the measurement.
- **[[feedback_persisted_runs_are_audit_trail_smokes_are_not]]** — the ADR's verification consequence chain wants persisted runs, not smoke tests. Each verification step above produces a live observation logged in the journal or the blackboard, not a one-off `python -c`.

---

## Step dependency graph

```
Step 0 (debug-mode instrumentation, permanent — Option 1)
   │
   ├──> Step 1 (schema + classification) ──┐
   │                                       │
   │                                       v
   │   [Open call #4: P6 consolidation decision] ──> sibling ADR? ──┐
   │                                                                │
   │                                       ┌────────────────────────┘
   │                                       │
   └──> Step 2a (CLI flag) ──> Step 2b ──> Step 2c (systemd split)
                                                  │   (single operational restart;
                                                  │    audit blackout closed here)
                                                  v
                                            Step 3a-telemetry
                                            (logging.Handler over
                                             asyncio slow-callback
                                             warnings → blackboard)
                                                  │
                                                  v
                                            Step 3b-rule
```

- **Step 0 must land first.** Everything downstream depends on its evidence. **Step 0 is permanent infrastructure** per Open call #3 Option 1 — its debug-mode enablement is the only low-level source CPython provides for loop-hold timing, and Step 3a-telemetry subscribes to its emission path rather than replacing it.
- **Step 1 must land before Step 2a's exclude-dedicated default has anything to filter on.** Otherwise `--only` rejects every stem (none have `true` yet) and exclude-dedicated finds nothing to exclude (current behavior). Step 2a's CLI surface may land in the same change as Step 1; just don't run `daemon up` against pre-Step-1 code with the new defaults.
- **Open call #4 must resolve before Step 2c.** P6's consolidation-vs-split decision changes whether Step 2c enables 1 template instance or 8. Steps 0/1/2a/2b are not blocked by it.
- **Step 2a, 2b, 2c land as one operational restart.** The systemctl-touching restart happens at 2c only; 2a and 2b are code-only landings that do not require a `daemon restart`. This closes the audit-blackout window Big Brother flagged in round 1.
- **Step 2b is concurrent with 2a, must precede 2c.** The cooperative-yield edits must be in place before systemd starts SIGTERM-ing heavy daemons on `daemon restart`.
- **Step 3a-telemetry runs after Step 2c.** It needs the split topology to measure under. Step 3a is additive on top of Step 0 — it does not revert anything.
- **Step 3b-rule runs after Step 3a-telemetry.** It consumes the structured `loop_hold.sample` entries 3a produces.

---

## Tracking checklist

- [ ] **Step 0** — `set_debug` + `slow_callback_duration_sec` added to `daemon:` section of `.intent/enforcement/config/operational_config.yaml` + `DaemonConfig` fields + gated enablement in `_run_daemon_locked`. Daemon restart; 30-min journal observation; confirm heavy workers surface as slow callbacks. **Attribution check:** journal warnings show ≥2 distinct `audit_sensor_*` task names (gates whether Step 3a's regex design is viable or needs contextvars-based task-name injection). **Permanent infrastructure per Option 1.**
- [ ] **Open call #1** — Postgres pool sizing for 10 daemons; document in this file before Step 2c.
- [ ] **Open call #2** — `PartOf` cascade decision for the template unit; document in this file before Step 2c.
- [ ] **Open call #3** — RESOLVED v3: Option 1 selected (debug-mode permanent, Step 3a structures the output). Governor confirms before Step 3a-telemetry handler lands; may override toward Option 2 (custom event loop) if standing debug overhead measures unacceptable.
- [ ] **Open call #4** — Consolidation (Path A, sibling ADR) vs accept-8×-reparse (Path B) for the audit_sensor cluster; decide before Step 2c.
- [ ] **Step 1** — `requires_dedicated_process` field in `worker.schema.json`; classify 8 audit sensors (per Step-0 evidence); embedder carve-out confirmed (grep test).
- [ ] **Step 2a** — `--only <stem>` flag; exclude-dedicated default; per-stem PID lock; refusal paths tested. **Code-only; no `daemon restart`.**
- [ ] **Step 2b** — Cooperative-yield edits in `AuditViolationSensor`; SIGTERM-completes-cleanly verification. **Code-only; no `daemon restart`.**
- [ ] **Step 2c** — Template unit authored (governor task); N template instances enabled (N = 1 or 8 per Open call #4); `_SYSTEMD_UNITS` dynamic; `daemon status` shows expected row count; #519 sub-second graceful shutdown; lightweight workers' p50 within 1.05× declared. **This is the single operational `daemon restart` of Step 2.**
- [ ] **Step 3a-telemetry** — `_SlowCallbackBlackboardHandler` installed on asyncio logger; `loop_hold.sample` blackboard subject populating; handler exception path verified; handler emission cost does not itself trigger slow-callback warnings.
- [ ] **Step 3b-rule** — `runtime.worker_process_classification` rule + engine reading `loop_hold.sample`; `WorkerClassificationConfig` dataclass; advisory finding lifecycle confirmed.
- [ ] **Post-completion** — ADR-081 Verification section walked end-to-end; status remains Accepted; this planning file moved to `.specs/planning/archive/` per project convention.

---

## What this plan does NOT decide

- Whether to migrate from Option 1 (structured sink over `set_debug`'s slow-callback warnings) to Option 2 (custom event-loop subclass) if the standing debug-mode overhead measures unacceptable post-Step-0. Open call #3 selected Option 1; the migration question is left for future review under measured evidence, not pre-decided here.
- The exact `await asyncio.sleep(0)` cadence inside `AuditViolationSensor` (per-file or every-N-files — measured under Step 0).
- Whether `runtime.worker_process_classification` should eventually become blocking (it does not, per D7 — and this plan does not propose changing that).
- Future-generation isolation primitives (container-per-worker, k8s-per-worker) — the ADR notes those inherit the primitive cleanly; out of scope here.

---

## References

- ADR-081 — the decision this plan implements.
- Issue #518 — framing motion.
- Issue #519 — graceful-shutdown lag; the verification signal Step 2c depends on.
- Issue #516 / #517 — `max_interval` tuning thread the ADR retires; #517's re-tune scope shrinks materially under this plan.
- ADR-041 — per-worker liveness threshold precedent (the constitutional shape Step 1 follows).
- ADR-069 D8 — graceful claim-release in `Worker.start()` `finally` — the contract Step 2b's edits preserve unchanged.
- Commit `f55c83f9` — singleton PID lock + `core-admin daemon up/down/restart/status` wrappers; the foundation Step 2c extends.
- Memory [[feedback_event_loop_starvation_diagnostic]] — the diagnostic discipline the ADR encodes structurally.
- Memory [[feedback_honesty_gated_audit]] — the audit-baseline check applied after each step.
- Memory [[feedback_orphan_daemon_pretest]] — the pre-verification hygiene check.
