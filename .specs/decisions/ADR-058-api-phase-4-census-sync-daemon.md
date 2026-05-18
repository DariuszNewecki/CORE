# ADR-058 — API Phase 4: /census + /sync + /daemon

**Status:** Accepted
**Date:** 2026-05-18
**Authors:** Darek (Dariusz Newecki)
**Parent:** ADR-053 (API as Governance Interface)
**Relates to:** ADR-054 (Phase 1), ADR-055 (Phase 2), ADR-057 (Phase 3),
ADR-018 (VectorSyncWorker), ADR-041 (worker liveness thresholds)

---

## Context

ADR-053 D4 defines Phase 4 as the final capability cluster: `/census`
(Body CIM services), `/sync` (Will sync workflows), and `/daemon` (Worker
lifecycle). Accepting this ADR completes the papers-first sequence across
all ten namespaces and gates Phase 4 implementation per ADR-053 D6.

Phase 4 is architecturally distinct from Phases 1–3 in two ways:

**`/daemon` self-reference.** The API runs inside the daemon. `POST
/daemon/stop` is therefore a request to the API to terminate its own host
process. This requires explicit treatment — a naive handler that kills its
own process mid-response produces undefined behaviour. The design decision
is in D3 below.

**`/sync` multiplicity.** The four sync operations (`db-registry`, `vectors`,
`code-vectors`, `dev-sync`) share a common character — they are stateful,
potentially slow operations with a write-flag discipline — but they are
backed by different Body/Will services. A single `sync_runs` table with a
`sync_type` discriminator is the right model, following the precedent that
`fix_runs` uses `fix_id` to distinguish operation type.

**Unassigned capability map items.** Two CLI files — `components.py`
(`GET /components`) and `search.py` (`GET /search/capabilities`,
`GET /search/commands`) — do not map to any of the ten ADR-053 D4
namespaces. They are currently in scope for CLI extraction but have no
Phase ADR home. They are noted here as an open item; Phase 4 implementation
does not cover them. A follow-up ADR or amendment to ADR-053 must assign
them before CLI extraction is complete.

**CLI files in scope (Phase 4 migration targets):**

Source: capability map at `.specs/planning/CORE-API-capability-map-2026-05-16.md`.
Exact import verification via live grep to `var/adr058-phase4-imports.txt`
before implementation begins (D7).

`/census`:
- `src/cli/commands/inspect/repo_census.py` — CIM census with snapshot/
  baseline/diff support; `body.*`, `shared.*` imports

`/sync`:
- `src/cli/commands/fix/db_tools.py` — CLI command tree → DB, bidirectional
  PG↔Qdrant; `body.*`, `shared.*` imports
- `src/cli/commands/dev_sync.py` — fix + DB + vector composite workflow;
  `body.*`, `shared.*` imports
- `src/cli/resources/vectors/sync.py` — constitution vector sync;
  `shared.*` import
- `src/cli/resources/vectors/sync_code.py` — codebase symbol embedding;
  `shared.*` import
- `src/cli/commands/run.py` — worker pipeline vectorisation trigger

`/daemon`:
- `src/cli/commands/daemon.py` — background worker daemon lifecycle;
  broad system access

---

## Decisions

### D1 — Census operations: `census_runs` resource table

`POST /census/runs` triggers a CIM-0 structural census — a potentially
slow operation that traverses the full repository tree and produces a
`RepoCensus` artifact. A new table `core.census_runs` is introduced.

`POST /census/baselines/{name}` creates a named baseline from a prior
census run. It is synchronous (the baseline record is small and written
immediately). Returns `200 OK` with the baseline record.

`GET /census/diff` is a read-only query comparing two census snapshots.
Synchronous. No new table.

`core.census_runs` schema (minimum):
```
census_run_id     uuid PRIMARY KEY DEFAULT gen_random_uuid()
status            text NOT NULL DEFAULT 'pending'
snapshot          boolean NOT NULL DEFAULT false
baseline_name     text                        -- if snapshot=true
created_at        timestamptz NOT NULL DEFAULT now()
updated_at        timestamptz NOT NULL DEFAULT now()
result            jsonb                       -- RepoCensus artifact
error             text
requested_by      text NOT NULL DEFAULT 'system'
requested_at      timestamptz NOT NULL DEFAULT now()
request_ref       text
```

### D2 — Sync operations: `sync_runs` resource table with discriminator

All four sync operations share a single `core.sync_runs` table, using
`sync_type` as the discriminator. This follows the `fix_runs` precedent:
different operation types share one lifecycle table, distinguished by a
type column. No new table per operation type.

`sync_type` values: `db_registry` | `vectors` | `code_vectors` | `dev_sync`

All four are async operations (vectorisation and DB sync can be slow).
All four respect the `write` flag per ADR-014 dry-run-first discipline.

`core.sync_runs` schema (minimum):
```
sync_run_id       uuid PRIMARY KEY DEFAULT gen_random_uuid()
sync_type         text NOT NULL               -- discriminator
status            text NOT NULL DEFAULT 'pending'
write             boolean NOT NULL DEFAULT false
target            text                        -- optional scope filter
created_at        timestamptz NOT NULL DEFAULT now()
updated_at        timestamptz NOT NULL DEFAULT now()
result            jsonb                       -- counts, changed items
error             text
requested_by      text NOT NULL DEFAULT 'system'
requested_at      timestamptz NOT NULL DEFAULT now()
request_ref       text
```

`POST /sync/dev-sync` is the composite workflow (fix → db-registry →
vectors). Its `result` payload includes per-phase outcomes. It does not
chain through `fix_runs` — it records the composite run as a single
`sync_runs` row with `sync_type='dev_sync'` and a structured `result`
that names what each phase did.

### D3 — Daemon lifecycle: signal-based, synchronous, no resource table

`POST /daemon/start` and `POST /daemon/stop` are lifecycle signals, not
resource operations. No new table.

**Start:** delegates to `systemctl --user start core-daemon`. The API
handler invokes this via subprocess and returns `200 OK` with
`{ "status": "started" }` if the command succeeds, or `500` with an error
body if it fails. The API serving the request is a separate process from
the daemon when the daemon is not running, so there is no self-reference
hazard on start.

**Stop:** the self-reference problem. The handler cannot kill its own
process mid-response. The correct implementation: the handler sends
`systemctl --user stop core-daemon` asynchronously (fire-and-forget after
the response is sent) via a background task registered with FastAPI's
`BackgroundTasks`. The response — `200 OK` with `{ "status": "stopping" }`
— is sent first. The daemon stops cleanly after the response completes.
The client should expect the connection to close shortly after the `200`.

`GET /daemon/status` is added as a read-only companion — it returns current
daemon liveness, worker count, and per-worker health derived from
`WorkerShopManager` (ADR-041 governed thresholds). Synchronous, `200 OK`.

**No auth guard on `/daemon/*` for Phase 4.** Inherited from ADR-054 D3
loopback-only posture. Auth on daemon lifecycle is deferred to the auth ADR.

### D4 — Endpoint surface

```
# /census
POST /census/runs                   Async: CIM-0 structural census
GET  /census/runs/{id}              Poll census_run status and RepoCensus result
POST /census/baselines/{name}       Sync: create named baseline from prior run
GET  /census/baselines              List all named baselines
GET  /census/diff?baseline=...      Sync: diff current (or named) run vs baseline

# /sync
POST /sync/db-registry              Async: CLI command tree → PostgreSQL
POST /sync/vectors                  Async: bidirectional PG↔Qdrant
POST /sync/code-vectors             Async: vectorise codebase via worker pipeline
POST /sync/dev-sync                 Async: fix + db-registry + vectors composite
GET  /sync/runs/{id}                Poll sync_run status and result

# /daemon
POST /daemon/start                  Sync: start daemon via systemd
POST /daemon/stop                   Sync: signal daemon to stop (fire-and-forget)
GET  /daemon/status                 Sync: liveness, worker count, per-worker health
```

All endpoints conform to the ADR-053 D3 protocol contract.

### D5 — Unassigned namespace items flagged for follow-up

`components.py` (`GET /components`) and `search.py` (`GET
/search/capabilities`, `GET /search/commands`) have no assigned namespace
in ADR-053 D4. These files carry direct `body.*` / `shared.*` imports and
will block CLI extraction if unresolved. A follow-up ADR or ADR-053
amendment must assign them to a namespace (candidates: extend `/inspect`,
extend `/audit`, or introduce a `/meta` namespace). This is not a Phase 4
blocker but is a CLI-extraction blocker.

### D6 — No auth; loopback binding (inherited from ADR-054 D3)

Phase 4 inherits the ADR-054 D3 auth posture unchanged. Loopback-only
binding. Auth promotion trigger unchanged.

### D7 — Phase 4 completion verified by suppress-entry removal

Before implementation begins, a live grep enumerates all Phase 4 files
carrying direct `body.*`, `will.*`, `mind.*`, or `shared.*` imports.
Result saved to `var/adr058-phase4-imports.txt`. That file is the
authoritative D7 list; the Context section above is an approximation.

At Phase 4 closure, no suppress entries for `architecture.cli.api_only`
may remain in any D7 file.

### D8 — Phase 4 closure completes the ADR-053 migration surface

Phase 4 closure is the trigger for ADR-053 D5 ("CLI becomes a typed HTTP
client"). At that point: all ten namespaces have API endpoints; all D7
files across all four phases have zero direct CORE imports; `src/cli/`
can be extracted per the ADR-050 resolution sequence. The tracking issue
for the unassigned items (D5 above) must be resolved or explicitly
accepted as deferred before extraction begins.

---

## Deferred

Nothing within the ten defined namespaces remains after Phase 4. The open
item is the unassigned `/components` and `/search` capability map items
(D5). These are deferred to a follow-up ADR.

---

## Verification

This ADR is verified when:

1. All endpoints in D4 exist, start without error, and return governed
   responses per the ADR-053 D3 protocol contract.
2. `POST /census/runs` produces a `RepoCensus` result retrievable via
   `GET /census/runs/{id}`.
3. `POST /census/baselines/{name}` and `GET /census/diff` are covered by
   tests including a missing-baseline 422 case.
4. All four `POST /sync/*` endpoints are covered by tests for both
   `write=false` (dry-run) and `write=true` paths.
5. `POST /daemon/stop` returns `200` before the daemon stops; the daemon
   stops cleanly after the response completes. Covered by an integration
   test using a test daemon process.
6. `GET /daemon/status` returns governed worker health data derived from
   ADR-041 thresholds.
7. All files in `var/adr058-phase4-imports.txt` import exclusively from
   `api.*` — no `body.*`, `will.*`, `mind.*`, or `shared.*` imports remain.
8. `core-admin code audit` reports no new findings introduced by Phase 4.
9. `core.census_runs` and `core.sync_runs` exist in `db_schema_live.sql`
   and the ORM.
10. A follow-up issue for the unassigned `/components` and `/search` items
    (D5) is open on GitHub before Phase 4 is marked complete.

---

## References

- ADR-053 — parent; D4 (phase map), D5 (CLI migration target), D6
  (papers-first gate)
- ADR-050 — CLI positioning; extraction sequence; this ADR's completion
  is the trigger for extraction
- ADR-054, ADR-055, ADR-057 — prior phases; pattern reference
- ADR-018 — VectorSyncWorker retired; `sync.vectors.code` action retained
  for manual invocation via `POST /sync/code-vectors`
- ADR-041 — worker liveness thresholds; governs `GET /daemon/status`
  health data
- ADR-014 — dev-phase priority; `write` flag on all `/sync/*` endpoints
- `src/body/services/cim/models.py` — `RepoCensus` artifact schema
- `src/cli/commands/daemon.py` — daemon lifecycle backend
- `src/cli/commands/dev_sync.py` — composite dev-sync workflow backend
- `src/cli/commands/fix/db_tools.py` — db-registry and vector sync backend
