---
kind: adr
id: ADR-039
title: ADR-039 — Audit-input cache invalidation
status: accepted
---

<!-- path: .specs/decisions/ADR-039-audit-input-cache-invalidation.md -->

# ADR-039 — Audit-input cache invalidation

**Status:** Accepted
**Date:** 2026-05-12
**Authors:** Darek (Dariusz Newecki)
**Closes:** #298
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


## Supplement — 2026-05-16 (commit 175b46e4)

**Stale AST cache gap — `_AST_CACHE` not cleared by `invalidate_file_cache()`.**

ADR-039 extended `invalidate_file_cache()` to clear `_file_list_cache`,
`_rel_path_map`, and `_pattern_cache`. A second-order cache was missed:
`_AST_CACHE: dict[Path, ast.AST]` (audit_context.py:53), populated by
`get_tree()` on first access and never cleared at audit cycle boundaries.

`clear_knowledge_graph_cache()` (audit_context.py:57) clears it but has
zero call sites in `src/` — effectively dead code. In practice, the only
thing clearing `_AST_CACHE` was daemon restart.

**Effect:** `ast_gate` reads source fresh from disk but evaluates a stale
parsed tree from the prior cycle. Affects all AST-gate rules that consume
`context.get_tree()` — not only `purity.docstrings.required`. Estimated
scope: ~14 rules silently evaluating pre-write ASTs since the cache was
introduced.

**Fix:** `_AST_CACHE.clear()` added inside `invalidate_file_cache()`.
Existing call sites at `filtered_audit.py:143` and `auditor.py:87`
inherit the broader invalidation automatically. Re-parse cost per cycle:
~700 files — trivial against rule-execution wall-time.

`_KNOWLEDGE_GRAPH_CACHE` deliberately excluded — DB-backed via
`DbSyncWorker` on its own cadence; clearing on every audit forces an
unnecessary DB round-trip.

**Concurrency note:** `_AST_CACHE.clear()` shares the same
shared-context race surface as `_file_list_cache` (two concurrent
sensors, one `AuditorContext`). Result of a race: degraded performance
on re-parse, not correctness. This surface pre-exists this fix and is
not widened by it.


## Supplement — 2026-06-15 — Change-gated invalidation (Option B′)

> **SUPERSEDED by the 2026-06-15 (rev. b) supplement below — Content-addressed
> parse cache (Option E).** B′ (a cycle-level digest gate) was found to be a
> coarse approximation of content-addressed caching, which CORE's existing
> `_AST_CACHE` already wants to be. Retained here for the reasoning trail; the
> measured cost and trust analysis below remain valid, but the *mechanism* of
> record is Option E, not B′.

**The per-cycle reparse cost, ruled "trivial" above, became the dominant
load at fleet scale.**

### Observed cost

On a 4-core host, the running daemon fleet (~9 process-isolated audit
sensors, one process per rule namespace) sat at **~244% aggregate CPU**,
load average ~3.3. Each sensor's per-cycle line read
`rescanned 969 files, 209 rules loaded`; a single `audit_sensor_style`
scan measured 2.5–5 min of CPU-bound AST parsing inside its 600s cycle
(~30–50% duty cycle, matching its measured ~32%). With five sensors on
the 600s cadence their multi-minute scans overlap, so 2–4 sensors are
parsing the full tree at almost any instant. `WARNING:asyncio:Executing
<Task ...> took ...` slow-callback warnings confirm the synchronous parse
blocks the event loop.

This is the cost Option B accepted as "~10ms / cycle, trivial" (rglob
only) and the 2026-05-16 supplement re-affirmed as "trivial against
rule-execution wall-time" (after adding `_AST_CACHE.clear()`, i.e. a full
969-file reparse). Both estimates held for *one* sensor; neither
anticipated **~9 process-isolated sensors each independently re-parsing
the same tree with no shared cache between processes**. The N× redundancy
is the regression.

### The waste

Over a 6-hour window the findings output barely moved: the modal cycle
reported `0 findings`, and the non-zero cycles reported *stable* counts
(the same 6/7/8/17 violations re-discovered identically every cycle).
Because `invalidate_file_cache()` is called **unconditionally** at cycle
entry (`audit_violation_sensor.py:152`), the fleet re-derives — at full
cost — an answer that did not change. On a mostly-static tree, ~100% of
the CPU produces zero new signal.

### Decision

Refine Option B to **Option B′ — per-cycle invalidation gated on a
change-probe.** Before invalidating and reparsing, the cycle computes a
cheap **input digest** over its audited surfaces. If the digest is
unchanged from the prior cycle, the cycle **skips** `invalidate_file_cache()`
and the reparse, and re-posts the prior cycle's findings (or a
`no-change` report). If the digest advanced, it invalidates and reparses
exactly as Option B does today.

This is Option D (invalidate-on-change) realized in **pull** form: the
probe runs inline in the existing cycle, so there is no separate watcher
process to die silently — the failure mode for which Option D was
originally rejected. It is not a TTL (Option C): there is no tunable; the
source of truth is the filesystem state itself.

### Trust analysis (load-bearing — this supplement stands or falls here)

ADR-039's guarantee is unchanged: **a violation hides for at most one
sensor interval, never the daemon's lifetime.** The gate preserves it:

- The reparse is skipped **only when the audited inputs are provably
  identical** to the prior cycle. Rule execution is deterministic over
  its inputs, so identical inputs ⇒ identical findings; re-posting the
  prior result is the *same* answer, not a weaker one.
- On any real change the digest advances, and the **next** cycle reparses.
  The drift window is still exactly one sensor interval — it is **not**
  widened. The silent-blindness failure mode this ADR closed stays closed.

The gate is trust-preserving **if and only if** the digest is *sound*,
which imposes two non-negotiable conditions:

1. **Both surfaces.** The digest MUST cover both audited inputs ADR-039
   separates: the source-file set/content reachable through the sensor's
   artifact globs **and** the `.intent/` policy + rule content loaded via
   `IntentRepository`. A git-`HEAD` check alone is **unsound** — the
   daemon also observes uncommitted working-tree edits — so the probe is a
   stat manifest (sorted `(relpath, size, mtime_ns)` over both trees,
   including additions and deletions), not a commit check.
2. **Fail toward reparse.** Any error, ambiguity, or unreadable input in
   computing the digest MUST force the full reparse. The gate may only
   ever *save* work, never *suppress* an audit under uncertainty.

**Accepted residual:** a file whose content changes while its size *and*
mtime both stay identical would be missed. This is the same data git
itself trusts for dirty-detection, and the originating 2026-05-11 incident
(a newly-added file) is detected by it. We accept this boundary; a
governor wanting zero residual can escalate the manifest from stat to a
content hash (read-and-hash, no parse — still far cheaper than parsing),
which this supplement permits but does not require.

### Implementation guidance

1. Add an `AuditorContext.input_digest(globs)` (or equivalent) that stats
   the artifact-glob files and the `.intent/` tree and returns a stable
   digest. Stat-only by default; no parse.
2. In `AuditViolationSensor.run`, compute the digest **before**
   `audit_violation_sensor.py:152`. Persist the prior digest on the
   sensor instance (each sensor worker holds its own `core_context`, so no
   cross-worker synchronisation is needed — same assumption as the
   original Option B `reload()` note above).
3. On match: skip `invalidate_file_cache()` + reparse; re-post prior
   findings or a `no-change` report; **still `post_heartbeat()`** so
   liveness and the ADR-104 lease are unaffected.
4. On miss (or any digest error): proceed exactly as today.
5. **Observability:** the existing `rescanned N files, M rules loaded`
   line MUST distinguish the two paths — e.g. emit
   `audit_sensor_X: inputs unchanged (digest <short>), reparse skipped`
   on the skip path — so an operator can confirm the cycle saw fresh state
   and *decided* not to reparse, rather than silently doing nothing. A
   skip that looks identical to a stall would itself be a trust regression.

### Test obligation

The runtime-invariant test mandated by the original ADR (a file written
*during the same daemon process* must appear in the next scan) MUST
continue to pass unchanged — it is the regression guard for the trust
guarantee and the gate must not weaken it. Add a companion test: two
consecutive cycles over an untouched tree reparse once, not twice
(asserts the gate actually fires); and a third cycle after a single
`write_text` reparses (asserts the gate releases on change).

### Status

Decision recorded; implementation pending under proposal flow. Until
implemented, the unconditional per-cycle reparse remains in force; the
operational stopgap (raising `max_interval` on the 600s sensors, or
renicing the sensor processes) is orthogonal and does not require this
change.

**Superseded same day by the supplement below.** See Option E.


## Supplement — 2026-06-15 (rev. b) — Content-addressed parse cache (Option E)

**Supersedes the Option B′ supplement above as the mechanism of record.**
Same observed cost (~244% CPU, ~9 sensors re-parsing the full 969-file tree
every cycle); a sharper root cause; a mechanism that is cheaper than B′ and
fail-safe by construction rather than by guard.

### Root cause, restated

CORE already has a parse cache and throws it away every cycle. In
`src/mind/governance/audit_context.py`:

- `_AST_CACHE: dict[Path, ast.AST]` (L53) — keyed by **`Path`**.
- `get_tree()` (L441–449) — returns the cached tree on a path hit, else
  parses and stores by path.
- `invalidate_file_cache()` (L228) — calls `_AST_CACHE.clear()`, a
  **wholesale wipe at every cycle entry** (the 2026-05-16 supplement added
  this clear).

So the cache cannot help across cycles: every cycle re-parses all 969 files
even when one (or zero) changed. The blunt clear was chosen for
*correctness* — a path-keyed cache can return a parse from before a file
changed (the 2026-05-11 incident this ADR closed) — but it buys correctness
by discarding the entire reuse benefit. B′ then tried to recover some of that
benefit with a cycle-level "did anything change?" guard.

### Decision

**Option E — content-addressed parse cache.** Key the parse cache on the
*content identity* of each file, not its path, and stop clearing it
wholesale:

```
key = (path, content-hash)          # canonical
     | (path, mtime_ns, size)       # cheap stat proxy, same residual as B′
```

`get_tree()` returns a hit only when the key — i.e. the bytes — match;
otherwise it parses and stores under the new key. Eviction is by
capacity/LRU and on key-miss, never an unconditional per-cycle `clear()`.
`invalidate_file_cache()` no longer wipes `_AST_CACHE`; staleness is handled
by the key, not by clearing. Optionally, memoize one layer higher — cache
*findings* keyed `(content-hash, rule-id)` — to also skip rule evaluation on
unchanged files, not just parsing.

Effect: "rescanned 969 files" becomes "stat/hash 969, parse only the files
whose bytes changed." A typical commit touching a handful of files reparses a
handful, not the whole tree.

### Why Option E over B′ and over Option D (the watcher)

This ADR's invariant posture is: **detection must fail toward doing the
audit, never toward suppressing it.** Ranked against that posture:

- **Option D (filesystem watcher, rejected in the original ADR):** fails
  toward *silence* — a missed/overflowed/dead watcher means no audit fires,
  fleet-wide, while looking alive. Wrong direction for a trust system.
- **Option B′ (cycle-level digest gate):** safe *only if the guard is
  written correctly* — it is a predicate someone can get wrong, and it is
  coarse (any one changed file forces a full-tree reparse).
- **Option E (content-addressed cache):** **fail-safe by construction.** The
  cache never decides "should I audit?" — it only answers "have I already
  parsed *these exact bytes*?" A changed file has a different key and is
  *forced* to re-parse; a stale parse is impossible. Safety is a property of
  the data structure, not of a guard. And it is fine-grained: only changed
  files pay.

The one-sensor-interval drift guarantee is therefore preserved structurally:
the cache can only ever *save* re-parsing of byte-identical inputs, never
suppress the audit of a changed one.

**Residual.** With the cheap stat-proxy key, a content change at identical
`(mtime, size)` would hit a stale entry — the same residual B′ carried, and
the same data git trusts for dirty-detection. The canonical content-hash key
removes even that (read-and-hash is far cheaper than parse). Choose per
paranoia level; both fail safe relative to the watcher.

### Two levels (the #518 process-isolation wrinkle)

`_AST_CACHE` is a **per-process** global, and the audit fleet runs ~9
isolated sensor processes (#518). So:

- **Level 1 — content-key the existing per-process cache, drop the
  wholesale clear.** Smallest change, localised to `audit_context.py`.
  Eliminates the *per-sensor* redundancy immediately (each process reparses a
  changed file at most once). This is the recommended first step and likely
  the bulk of the win.
- **Level 2 — a shared content-addressed cache** across processes
  (DB- or disk-backed, `content-hash → parsed-or-findings`). Each changed
  file is parsed/evaluated **once for the whole fleet**, eliminating the ~9×
  cross-process duplication that is the true root of the measured load.
  Bigger lift — an `ast.AST` is not trivially serializable, so this most
  naturally caches *findings* keyed `(content-hash, rule-id)` rather than
  trees. `_KNOWLEDGE_GRAPH_CACHE`'s existing DB-backed posture (see the
  2026-05-16 note) is the precedent for where this lives.

### Relationship to the other mechanisms

- **B′ is withdrawn as a mechanism.** Option E dominates it: B′'s only edge
  was skipping rule-evaluation on a fully-static cycle, which the optional
  findings-cache in Option E recovers at per-file granularity.
- **The watcher (Option D) is optional and latency-only.** With Level 1 in
  place, cycles are cheap enough that a change-watcher buys only *promptness*
  (sub-interval detection), never correctness or efficiency. If ever added,
  it stays an accelerator atop the unconditional timer floor — never a
  replacement for it — for the fail-toward-silence reason above.

### Implementation guidance

1. **`audit_context.py`:** change `_AST_CACHE` key from `Path` to
   `(path, content-key)`; `get_tree()` computes the key (stat or hash) and
   hits only on match; remove `_AST_CACHE.clear()` from
   `invalidate_file_cache()` (file-list/pattern invalidation may remain — it
   is cheap and unrelated). Add capacity-bounded eviction so the cache cannot
   grow without limit across a long-lived daemon.
2. **Concurrency:** the shared-context race noted in the 2026-05-16
   supplement is unchanged in kind — a race degrades to a redundant parse,
   not a stale result, because the key is content-derived. Not widened.
3. **Level 2 (if pursued):** a `(content-hash, rule-id) → findings` table
   synced like other DB-backed caches; cache-miss path is the current full
   evaluation, so it fails safe.

### Test obligation

- The original runtime-invariant test (a file written *during the same
  daemon process* must appear in the next scan) MUST still pass — it remains
  the regression guard for the trust guarantee.
- Add a parse-reuse test: `get_tree(f)` twice with no change ⇒ second call is
  a cache hit (no reparse); mutate `f`'s bytes ⇒ next `get_tree(f)` reparses.
  This asserts both the saving (hit on identical bytes) and the safety
  (forced miss on changed bytes).
- Level 2 needs its own cross-process hit/miss test.

### Status

Mechanism of record for ADR-039's efficiency concern. Implementation pending
under proposal flow; Level 1 first. The `max_interval` stopgap (committed
`d12c1e51`) remains orthogonal interim relief and is reversible once Level 1
lands.

> **Corrected by the 2026-06-15 (rev. c) measurement supplement below.** Option
> E (Level 1) was implemented in `98c9f592`, but measurement afterwards showed
> its impact is ~2% of a cycle, not the dominant cost. The framing above (and
> the `98c9f592` commit message) overstated it. See rev. c for the real
> breakdown.


## Supplement — 2026-06-15 (rev. c) — Measurement correction: parsing was never the bottleneck

**The "rescanned 969 files" log line misattributed the cost. Option E (and the
2026-05-16 supplement before it) optimised input *parsing*; the dominant
per-cycle cost is rule *execution*.**

After committing Option E Level 1 (`98c9f592`), a measurement of one isolated
single-namespace audit (`style`, 2 rules, no cross-process contention)
produced:

| component | median per cycle | share |
| --- | --- | --- |
| `reload_governance` (`.intent/` reload) | ~1.3 s | ~1.4% |
| `src/` AST parse — COLD (pre-Option-E) | ~1.6 s | ~1.7% |
| `src/` AST parse — WARM (post-Option-E) | ~6 ms | ~0% |
| **rule execution** | **~91 s** | **~97%** |
| **total cold cycle** | **~94 s** | — |

(Standalone reference points: cold full-tree parse of 969 files ≈ 1613 ms,
warm ≈ 6 ms — a real 278× drop, but on a slice that is ~2% of the cycle.)

### Corrections to the record

1. **Option E / Level 1 is correct but minor.** It cuts parsing from ~1.6 s to
   ~6 ms per cycle — real, harmless, and it preserves the trust guarantee — but
   that is ~2% of a ~94 s cycle, **not** "the dominant cost." The `98c9f592`
   commit message and the rev. b framing above overstated its impact. Level 1
   is kept (the saving is real and the fail-safe property is worth having), but
   it is not the fix for the CPU problem.
2. **Level 1b (`.intent/` reload gate) is withdrawn as not worth doing
   standalone.** Measured at ~1.3 s/cycle (~1.4%); gating it would save about
   what Level 1 saves. The earlier claim that `.intent/` reload is "much
   cheaper than the parse" was wrong (it is comparable), but both are dwarfed
   by rule execution.
3. **The `max_interval` stopgap (`d12c1e51`) was the proportionate lever, not a
   sticking-plaster.** Halving cycle *frequency* cuts the ~91 s of rule
   execution proportionally — far more than removing the ~3 s of input-prep.
   Its standing should be upgraded from "interim relief" to "the actual
   first-order mitigation until rule-execution cost is addressed."

### Where the real cost is (not yet diagnosed)

Two `style` rules take ~91 s over the scoped file set. The cause is **not yet
established** and must be profiled, not assumed — candidates include per-rule
full-tree walks, per-file knowledge-graph or DB lookups inside the engines, or
redundant re-derivation across the two rules. The next investigation is to
profile `run_filtered_audit` rule execution for one namespace and attribute the
~91 s before proposing any further mechanism. No new optimisation should be
designed against the "parsing" narrative this supplement retires.

### Method note

Measured via direct timing of `AuditorContext.reload_governance`,
`get_tree` over `src/**/*.py`, and `run_filtered_audit(rule_patterns=[...])`
on the live repo (969 source files, 236 policies / 209 rules indexed), single
process. Wall-clock per sensor in production is larger again due to ~9-way
process contention on a 4-core host — which is why frequency reduction
(`max_interval`) and the cross-process redundancy are the levers that scale,
not input-prep caching.
