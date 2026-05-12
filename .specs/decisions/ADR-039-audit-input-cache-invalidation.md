<!-- path: .specs/decisions/ADR-039-audit-input-cache-invalidation.md -->

# ADR-039 — Audit-input cache invalidation

**Status:** Draft
**Date:** 2026-05-12
**Authors:** Darek (Dariusz Newecki)
**Closes:** TBD (open after governor review)
**Relates to:** ADR-030 (Daemon stale-code detection posture)

---

## Context

`AuditorContext` memoises two pieces of audit input on first use and never
invalidates them for the life of the process:

- `_file_list_cache` — the result of `repo_path.rglob("*.py")`, populated
  on the first call to `AuditorContext.get_files()`
  (`src/mind/governance/audit_context.py:103,150-154`).
- `_pattern_cache` — per-`(include, exclude)` filtered subsets, written
  once per cache key (`audit_context.py:105,145-146,222`).

A single `AuditorContext` instance lives on `core_context.auditor_context`
for the daemon's lifetime. Every audit-based sensor (`audit_sensor_purity`,
`audit_sensor_architecture`, `audit_sensor_logic`, `audit_sensor_modularity`,
`audit_sensor_layout`, `audit_sensor_style`, `audit_sensor_linkage`) shares
this instance and reads files through it on every 600s cycle.

The same shape applies to governance input. The daemon's
`IntentRepository` indexes 152 policies / 142 rules at startup
(`shared.infrastructure.intent.intent_repository`), and the loaded rule
set is held in memory for the process lifetime. Rules added to `.intent/`
after daemon boot are not enforced by the running loop.

### Observed incident (2026-05-11 → 2026-05-12)

`bd998c24` (ADR-038) introduced `src/will/workers/circuit_breaker.py` at
21:48 on 2026-05-11. The class `CircuitBreakerConfig` was committed with
a missing stable ID anchor — a violation of `linkage.assign_ids` that the
on-demand auditor (`core-admin code audit`) reports as an ERROR.

The daemon process (PID 2002644) had been running since 2026-05-11 16:53
— ~5 hours before the new file landed. From 21:48 on 2026-05-11 through
07:03 on 2026-05-12 (~9 hours), `audit_sensor_linkage` ran 54 cycles, each
reporting "no actionable violations found". No `fix.ids` proposal was
generated for `circuit_breaker.py`. The autonomous remediation loop
appeared functional — workers ticked, heartbeats posted, sensors reported
clean — while a real violation accumulated in HEAD undetected.

Cause: every sensor cycle resolved `linkage.assign_ids` to its scope
`src/**/*.py`, called `context.get_files(...)`, and received the cached
file list snapshotted at 16:53 the previous day. `circuit_breaker.py` was
not in that snapshot. The rule was applied to zero relevant files and
correctly returned zero findings — for the data it could see.

Verification (2026-05-12 07:03 → 07:06): the daemon was restarted with a
fresh cache. Within 2 min 25 sec, the loop detected the violation,
generated `fix.ids` proposal `c636e048-2dd6-40`, executed it, and
committed the fix (`d9f51425`). The same restart cycle also cleared
backlog from three other post-16:53 violations
(`e47ffdf4`, `f56732fc`, `195b280c`).

This pattern — silent audit blindness for content added after daemon
boot — is the inverse of the failure mode ADR-030 protects against.

### Distinction from ADR-030

ADR-030 governs **loaded Python module drift**: when `src/` Python code
changes (action handlers, sensor implementations, rule logic), the
running daemon must DEGRADE and surface to the governor rather than
auto-reload, because a code deployment is a governor event and a
restart loop in the daemon's own startup path goes silent.

This ADR governs **audit-input data drift**: file lists scanned from
`src/` and rule content loaded from `.intent/`. These are *inputs* the
running audit code reads to do its job, not the audit code itself.
Treating them as code reload (DEGRADE, halt, governor restart) is
incorrect: every commit Claude lands under proposal flow adds files to
`src/`, and every new ADR / rule lands in `.intent/`. If new content
required a governor restart, A3 autonomous operation would halt after
every successful proposal.

The two surfaces need different policies. ADR-030 covers logic; this
ADR covers content.

---

## Options considered

**Option A — No cache. Re-scan disk every call.** Drop both
`_file_list_cache` and `_pattern_cache`. Each `get_files()` call rglobs.
Simplest possible model; eliminates the entire class of drift bug.
Cost: one rglob per rule per sensor cycle. The scan cost is trivial
against the audit work itself, but eliminates the reuse benefit for rules
that share the same scope within a single audit run — the original
optimisation is thrown away entirely.

**Option B — Per-cycle invalidation. Re-scan once per audit run.**
Invalidate both caches at the start of every `run_filtered_audit`
invocation (or equivalently, at the start of every sensor `run()`
method). Within a single audit cycle, all rules share the same fresh
snapshot. Across cycles, the snapshot is rebuilt. Drift window is
bounded to one sensor interval (600s, set in
`.intent/workers/audit_sensor_*.yaml`).

**Option C — TTL-based cache.** Cache with a configurable TTL (e.g.,
60s). Cheaper than Option B if multiple sensor cycles fire close
together, but introduces a tunable that has no natural source-of-truth
and is invisible to operators reading sensor output.

**Option D — Filesystem watch / commit hook.** Use `inotify` (or a
post-commit hook on the local git repo) to invalidate on actual change.
Most efficient — caches refresh exactly when needed. Adds a new
infrastructure dependency, a new failure mode (watcher dies silently),
and platform variance (inotify is Linux-specific).

---

## Decision

**Option B — per-cycle invalidation.**

`AuditorContext` exposes a public `invalidate_file_cache()` method that
clears `_file_list_cache`, `_rel_path_map`, and `_pattern_cache`.
`run_filtered_audit` (`src/mind/governance/filtered_audit.py:108`) and
`ConstitutionalAuditor.run_full_audit_async`
(`src/mind/governance/auditor.py:69`) call it once at entry, before any
rule executes. Within an audit run, the rebuilt cache is reused across
rules; across runs, it is rebuilt.

`IntentRepository` follows the same posture: a `reload()` method, called
once per audit-sensor cycle from `AuditViolationSensor.run`
(`src/will/workers/audit_violation_sensor.py:105`), refreshes the policy
and rule index from `.intent/`. The 600s sensor interval bounds the
maximum governance-drift window.

Rejected: Option A wastes the cache's reuse benefit within a single
audit run. Option C introduces a tunable with no natural value. Option D
adds infrastructure for a marginal efficiency gain over Option B.

---

## Consequences

**Positive:**
- The autonomous loop's audit detection becomes commit-aware. New files
  and new rules are visible to the next sensor cycle without operator
  action.
- The "silent blindness" failure mode disappears. The longest a
  violation can hide is one sensor interval, not the daemon's lifetime.
- The cache's original optimisation (rules in one audit run share the
  scan) is preserved; only cross-run reuse is dropped.
- No new infrastructure: no file watcher, no commit hook, no scheduler
  changes. The invalidation point is a single call at run entry.

**Negative:**
- Per-cycle rglob cost is now paid every sensor interval. For ~700 .py
  files in `src/` and a typical sensor cadence, this is ~10ms / cycle —
  trivial against the audit work itself, but worth measuring on the
  first deployment.
- Governance reload widens the surface where an in-flight cycle could
  observe a partial update (e.g., a new rule file present but its
  enforcement mapping not yet written). Mitigation: `IntentRepository`
  already validates documents at load (`intent_validator`), so a
  partial state surfaces as a load warning rather than a malformed
  rule executing.

**Neutral:**
- Drift window shifts from "daemon lifetime" to "one sensor interval".
  For audit sensors that is 600s. Within that window the loop is still
  blind to newly-landed content, which is acceptable because the
  remediation loop's own cycle is the same length.

---

## Implementation guidance

The change is mechanical and localised:

1. **`AuditorContext` (audit_context.py):** add
   `invalidate_file_cache()` that sets `_file_list_cache = None`,
   clears `_rel_path_map` and `_pattern_cache`. Public method, no
   constructor change.

2. **`run_filtered_audit` (filtered_audit.py:108):** call
   `context.invalidate_file_cache()` at function entry, before
   `extract_executable_rules`.

3. **`ConstitutionalAuditor.run_full_audit_async` (auditor.py:69):**
   call the same invalidator at entry. This keeps on-demand and
   sensor-driven audits behaviourally identical.

4. **`IntentRepository` (intent_repository.py):** add a `reload()`
   method that re-runs `initialize()` from a clean slate. Re-emit the
   "indexed N policies and M rules" log line so cycle-to-cycle drift
   is visible in journald. `reload()` must be safe to call from a
   single async task per sensor cycle; because each sensor worker holds
   its own `core_context` (and therefore its own `IntentRepository`
   instance), concurrent calls from different sensor workers do not
   share state and require no additional synchronisation. If a future
   refactor moves to a shared `IntentRepository` across workers, this
   assumption must be re-examined and a lock or copy-on-reload strategy
   introduced at that point.

5. **`AuditViolationSensor.run` (audit_violation_sensor.py:105):** call
   `intent_repository.reload()` before `_resolve_rule_ids`. Equivalent
   call sites: `TestCoverageSensor`, `TestRunnerSensor` if they read
   governance config (`test_coverage.yaml` etc.).

6. **Observability:** every cycle should emit a single-line summary at
   INFO level — `"audit_sensor_X: rescanned N files, M rules loaded"`
   — so an operator can confirm the cycle saw fresh state without
   reading the rest of the log.

A runtime invariant test belongs alongside this change: a sensor run
that follows a `repo_path.write_text("new_file.py", …)` *during the
same daemon process* must include the new file in its scan. This
captures the regression that would re-introduce the silent-blindness
failure mode.

---

## References

- ADR-030 — Daemon stale-code detection posture (covers loaded-module
  drift; this ADR covers data drift)
- `src/mind/governance/audit_context.py:96-222` — cache lifecycle
- `src/mind/governance/filtered_audit.py:108-199` — primary audit entry
- `src/will/workers/audit_violation_sensor.py` — sensor cycle
- Incident: `bd998c24` introduced violation 21:48 2026-05-11; daemon
  blind ~9 hours; `d9f51425` self-healed within 2 min 25 sec of
  restart on 2026-05-12 07:04
- `.intent/workers/audit_sensor_*.yaml` — 600s `max_interval` per
  sensor declaration (the drift-window bound this ADR establishes)
