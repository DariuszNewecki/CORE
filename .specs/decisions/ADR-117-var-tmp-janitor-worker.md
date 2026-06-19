---
kind: adr
id: ADR-117
title: ADR-117 — var/tmp is ephemeral scratch with no janitor: a bounded, age-gated reaper worker
status: proposed
---

<!-- path: .specs/decisions/ADR-117-var-tmp-janitor-worker.md -->

# ADR-117 — var/tmp has no janitor: a bounded, age-gated reaper, ramped report-first

**Status:** Proposed — 2026-06-19
**Date:** 2026-06-19
**Relates:** ADR-070 D8 (destructive autonomous loops need row/quantity caps in the same
change — the rails precedent this applies); ADR-071/ADR-106 (per-execution action
sandboxes under `var/tmp/` — a creator that already self-cleans, so NOT this worker's
target); ADR-039 (audit `get_files` walks the repo — stale scratch inflates the walk,
part of why an unbounded `var/tmp` is a real cost, not just untidiness); ADR-103
(`max_interval` cap — the schedule lives within it).
**Supersedes:** nothing.

---

## Context

`var/tmp/` is CORE's repo-internal **ephemeral-scratch** surface. The CLAUDE.md `/tmp`
prohibition routes *every* temp write here (`FileHandler` classifies `var/tmp/` as
`ephemeral-scratch`; `runtime_validator` and `ruff_linter` point their
`TemporaryDirectory(dir=...)` here; ad-hoc session scripts land here). **Nothing reaps
it.**

Observed 2026-06-19: 974 entries / 17 MB. Decomposition:
- **848** `probe-*` dirs — a *one-time* burst on 2026-06-07 (11:45–13:33) from an ad-hoc
  CLI-import probe using `mkdtemp(prefix="probe-")` with no cleanup. **No code in the
  current tree creates `probe-`** — it is dead residue, not a live leak.
- **~118** files — manual session scratch (`verify_*.py`, `*_update.md`, …).
- **0** leaked `core_canary_*` / action-sandbox dirs — CORE's own `TemporaryDirectory`
  and ADR-071/106 sandboxes self-clean; they leak only on a hard process kill.

So the steady-state leak is *small* but *unbounded over time*, and the floor of "nothing
ever reaps `var/tmp`" means residue accretes until a human notices and sweeps it (done
manually 974→4 on 2026-06-19). That is a standing janitorial obligation — exactly a
worker's job — but the worker *deletes*, so it is a destructive autonomous surface and
must be built with rails, not bolted on after.

## Decision

**D1 — A scheduled reaper worker.** Add `var_tmp_janitor` (`.intent/workers/`), a
deterministic, no-LLM, `governance`-class worker (the `observer_worker` system-state
reporter precedent — *not* `sensing`, which the schema reserves for audit-rule sensors).
It scans `var/tmp/`, identifies stale entries, and posts a Blackboard report every run
(≥1 entry per run, per the worker contract).

**D2 — Age gate is the primary rail.** Only top-level `var/tmp/` entries whose mtime is
older than `RETENTION_DAYS` (**7**) are candidates. The age floor *structurally* protects
in-flight work: an active action-sandbox or a live `core_canary_*` mid-validation is
always recent, so it can never be a candidate. If an entry's mtime cannot be read, it is
**skipped** (fail-closed), never selected. Selection is a pure function
(`find_reap_candidates`) so the predicate is unit-testable without the daemon.

**D3 — Bounded, boundary-checked deletion (ADR-070 D8 applied).** Per-run deletion cap
`MAX_REAP_PER_RUN` (**200**); excess waits for the next run (and is reported). Every
target's resolved path MUST be under `repo_root/var/tmp/` (a hard boundary assertion —
refuse anything resolving elsewhere, e.g. via a symlink). The worker never deletes
`var/tmp/` itself.

**D4 — Governed deletion surface (Phase 2).** When deletion is enabled, it routes through a
new `@atomic_action` `tmp.reap` (`impact` dangerous; declared `dangerous` in
`action_risk.yaml`, matching `secrets.delete` / `fix.purge_legacy_tags`), which calls
`FileHandler.remove_tree` / `remove_file`. No raw `os.remove` / `shutil.rmtree` in the
worker.

**D5 — Ramp-arc rollout (report-first → reaping; the destructive-needs-proof lesson).**
- *Phase 1 (this change):* the worker runs in **report-only** mode — it posts the reap
  *candidates* (count, oldest age, reclaimable bytes, how many a capped run would remove)
  and has **no deletion code path at all**. This proves the age/boundary predicate against
  live state before any byte can be removed.
- *Phase 2 (governor promotes after observation):* a bounded follow-up adds the `tmp.reap`
  atomic action (D4) and switches the worker from report-only to reaping under the D2/D3
  rails. It is a small, ADR-grounded change — **not a new ADR**.

**D6 — Exemption marker.** A top-level entry named `.keep`, or a directory containing a
`.keep` file, is never a candidate — so a deliberately-retained scratch dir survives
reaping.

**Schedule:** `max_interval` **21600s (6h)** — reaping is cheap and not latency-sensitive;
well within the ADR-103 cap.

## Consequences

- `var/tmp/` becomes self-bounding once Phase 2 lands; the manual 974→4 sweep stops being
  a thing a human has to remember.
- A new *autonomous destructive* surface is introduced — but age-gated, capped,
  boundary-checked, routed through a `dangerous` governed action, and **shipped
  report-only** so the predicate is proven before it deletes.
- Phase 1 artifacts: `var_tmp_janitor` worker (YAML + `src/will/workers/var_tmp_janitor.py`)
  and tests (predicate selects only stale/in-boundary entries; `.keep` exempted; recent
  entries kept; absent root is empty). Phase 2 adds `tmp.reap` (+ `action_risk.yaml` entry
  + `__init__` import) and the mode switch, with its own tests.
- **Not** addressed here: per-creator cleanup of `probe-*`-style ad-hoc bursts (none exists
  in-tree to fix); a future such harness should clean up after itself rather than lean on
  the janitor.
