---
kind: adr
id: ADR-147
title: 'ADR-147 — work/canary/ has no janitor: a bounded, age-gated reaper, deletes from day one'
status: accepted
---

<!-- path: .specs/decisions/ADR-147-canary-sandbox-janitor-worker.md -->

# ADR-147 — work/canary/ has no janitor: a bounded, age-gated reaper, deletes from day one

**Status:** Accepted — 2026-07-11
**Date:** 2026-07-11
**Relates:** ADR-117 (`var_tmp_janitor` — the report-first ramp pattern this ADR departs
from, and why); ADR-070 D8 (destructive autonomous loops need row/quantity caps in the
same change — the rails precedent this applies); ADR-097 D2 (target-class boundary
taxonomy — `work/` is not a declared prefix, a gap this ADR surfaces but does not close);
ADR-103 (`max_interval` cap — the schedule lives within it).
**Supersedes:** nothing.

---

## Context

`CrateProcessingService._run_canary_validation`
(`src/body/services/crate_processing_service.py`) creates a full repo snapshot under
`work/canary/sandbox_<crate_id>/` for every canary trial and relies solely on its own
`try/finally: shutil.rmtree(canary_repo_path, ignore_errors=True)` to remove it
afterward. There is no age-based backstop — identical in shape to the `var/tmp/` gap
ADR-117 closed, but for a different surface.

Discovered 2026-07-11: 1,948 orphaned `sandbox_fix_*` directories, ~14G, all dated
2026-06-23 through 2026-06-28. Root-caused to a systemd watchdog misconfiguration:
commit `f137682a` (2026-06-26) added `WatchdogSec=120` to `core-daemon.service` without
a corresponding `sd_notify(WATCHDOG=1)` call in the daemon, so systemd hard-killed
`core-daemon` with `SIGABRT` roughly every 131.5s for ~61 hours, auto-restarting each
time (fixed by the watchdog pinger added in commit `ebb85b33`, 2026-06-29). A hard
`SIGABRT` bypasses Python's `finally` entirely, so every sandbox in flight at kill time
was orphaned — repeatedly, across every restart, which explains both the volume and the
tight date clustering. The acute cause is already fixed; nothing prevents recurrence from
any other future hard-kill (OOM, `kill -9`, container eviction).

A second, independent bug compounded the damage: the snapshot's directory copy used
`shutil.copytree(item, dst, symlinks=False, ...)`, which *follows* symlinks and copies
their target's content instead of recreating the link. The repo-root `ITAM` symlink
(`-> /mnt/vector_db/YPTO/ITAM`) was thereby fully dereferenced into two of the orphaned
sandboxes, ballooning them to ~1.3G each against a normal ~6M sandbox size. Fixed in the
same change (`symlinks=True`); it multiplies the damage of any future orphan but is not
itself the retention gap this ADR addresses.

## Decision

**D1 — A scheduled reaper worker.** Add `canary_janitor` (`.intent/workers/`), a
deterministic, no-LLM, `governance`-class worker (the `var_tmp_janitor` /
`observer_worker` system-state-reporter precedent — not `sensing`). It scans
`work/canary/` every run and deletes stale sandbox directories, posting a Blackboard
report of what it reaped (≥1 entry per run, per the worker contract).

**D2 — Age gate plus a name-prefix scope guard are the primary rails.** Only top-level
`work/canary/` entries whose name starts with the fixed `sandbox_` prefix
`_run_canary_validation` always uses are ever candidates — anything else under
`work/canary/` is out of this worker's scope by construction, not by convention. Of
those, only entries whose mtime is older than `RETENTION_SECONDS` (**3600**, one hour —
far past any normal canary trial duration) are selected. An unreadable mtime is
**skipped** (fail-closed). Selection is a pure function (`find_stale_sandboxes`),
unit-testable without the daemon.

**D3 — Bounded deletion.** Per-run deletion cap `MAX_REAP_PER_RUN` (**50**); excess waits
for the next run. The worker never touches `work/canary/` itself, only its
`sandbox_`-prefixed children.

**D4 — Direct deletion, not routed through a governed `@atomic_action` (a deliberate
departure from ADR-117 D4).** ADR-117's Phase 2 design routes `var/tmp/` deletion through
a new `dangerous`-impact `@atomic_action` (`tmp.reap`) calling `FileHandler.remove_tree`,
specifically because `var/tmp/` classifies as `ephemeral-scratch` in
`.intent/taxonomies/target_class_boundaries.yaml` and FileHandler is the single
sanctioned mutation chokepoint. `work/` has **no entry** in that taxonomy at all — it
falls through to the `default: repo-source` classification, the *strictest* validation
tier, which is the wrong tier for a directory that is pure ephemeral trial scratch.
Declaring `work/` as `ephemeral-scratch` there is itself a `.intent/` (governed-artifact)
change requiring its own named governor confirmation, and was out of scope for this
change. Rather than force canary-sandbox cleanup through a taxonomy tier that
misclassifies it, `canary_janitor` uses `shutil.rmtree` directly — matching the existing,
already-shipped precedent in `_run_canary_validation`'s own `finally` block, which cleans
up the identical path the identical way. **Open item:** if the governor wants `work/`
brought under the FileHandler chokepoint uniformly, that is a follow-up ADR amending the
target-class taxonomy, not a blocker for this one.

> **Note (2026-07-13, #772):** the open item is closed. `.intent/taxonomies/
> target_class_boundaries.yaml` now declares `work/` (broad prefix — canary sandboxes plus
> the ~7 other subsystems that write ephemeral scratch under `work/`) as `ephemeral-scratch`,
> citing this D4 as grounding. No follow-up ADR was needed — the classification decision was
> already made here; only the taxonomy transcription was deferred. `canary_janitor`'s direct
> `shutil.rmtree` remains as-is (unaffected by this closure — see D4 above for why it bypasses
> FileHandler regardless of tier).

**D5 — No report-only ramp; deletes from day one (a deliberate departure from ADR-117
D5).** ADR-117 shipped `var_tmp_janitor` report-only first because `var/tmp/` can hold
arbitrary scratch content from many uncoordinated creators, so the age/boundary predicate
needed proving against live state before anything could be deleted. `work/canary/
sandbox_*` has a narrower, fully-known shape: it is created by exactly one call site
(`_run_canary_validation`), for exactly one purpose (a single trial's lifetime), and a
stale entry has zero retention value by definition — the incident that motivated this ADR
*is* the live-state proof (1,948 real orphans correctly identified as strictly the
`sandbox_`-prefixed, hour-plus-stale entries, nothing else). Skipping the report-only
phase here is a narrower-blast-radius call, not a lower bar for care: D2/D3 still apply
in full.

**D6 — No exemption marker.** Unlike `var_tmp_janitor`'s `.keep` convention, no sandbox
entry is ever intentionally retained — a canary trial has no reason to pin its own
scratch copy — so no exemption mechanism is provided.

**Schedule:** `max_interval` **1800s (30 min)** — tighter than `var_tmp_janitor`'s 6h,
since this surface can regrow considerably faster (one crate cycle per orphaned trial)
and the whole point is to bound how large a future orphan pile can get before it's
reclaimed.

## Consequences

- `work/canary/` becomes self-bounding against any future hard-kill of `core-daemon`
  mid-trial, independent of whatever caused the kill. The 2026-06-26/29 watchdog bug is
  already fixed; this ADR's worker is the backstop for the *next* unknown cause.
- Phase 1 *is* the deletion phase here (see D5) — there is no separate Phase 2 to land
  later, unlike ADR-117.
- Artifacts: `canary_janitor` worker (`.intent/workers/canary_janitor.yaml` +
  `src/will/workers/canary_janitor.py`) and tests (predicate selects only stale,
  `sandbox_`-prefixed, in-window entries; recent and non-`sandbox_` entries are never
  candidates; absent root is empty; `_reap` removes on success and reports failure
  without raising). A companion fix in the same change corrected the `symlinks=False`
  copytree bug (`crate_processing_service.py`), with its own regression test.
- **Not addressed here, and flagged as open items for the governor:**
  - `work/` has no `target_class_boundaries.yaml` entry and silently falls through to
    `repo-source` (the strictest tier) for any FileHandler-mediated write. This ADR does
    not add one; it only documents why `canary_janitor` bypasses FileHandler rather than
    operating under that misclassification.
  - `FileHandler.copy_repo_snapshot` (`src/body/infrastructure/storage/file_handler.py`)
    has the same `shutil.copytree` pattern without `symlinks=True` as the bug fixed here,
    at a different call site. Not touched by this change.
