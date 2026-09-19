-- 20260518_create_phase4_tables.sql
--
-- Creates the two resource tables backing ADR-058 Phase 4:
--
--   * core.census_runs — POST /census/runs (CIM-0 structural census)
--   * core.sync_runs   — POST /sync/{db-registry,vectors,code-vectors,dev-sync}
--                        with `sync_type` discriminator
--
-- /daemon endpoints intentionally have NO resource table — lifecycle
-- signals (start/stop/status) are synchronous and stateless. See
-- ADR-058 D3.
--
-- BACKGROUND
--
-- ADR-053 D2 established resource modelling for stateful API operations.
-- ADR-054 (audit_runs), ADR-055 (fix_runs), and ADR-057
-- (coverage_runs, refactor_runs, audit_remediation_runs) preceded this
-- migration. Phase 4 introduces the final two domain tables.
--
-- The single sync_runs table uses a `sync_type` discriminator following
-- the fix_runs precedent (one lifecycle table, type-tagged rows). The
-- four sync_type values — db_registry | vectors | code_vectors |
-- dev_sync — share the same write-flag discipline and async lifecycle.
--
-- Both tables follow the fix_runs lifecycle column conventions
-- (pending → executing → completed | failed):
--   id           uuid PK DEFAULT gen_random_uuid()
--   status       text NOT NULL DEFAULT 'pending'
--   requested_by text NOT NULL
--   requested_at timestamptz NOT NULL DEFAULT now()
--   started_at   timestamptz
--   finished_at  timestamptz
--   result       jsonb
--   error        text
-- plus per-domain columns described inline below.
--
-- FORWARD-ONLY. No rollback. Re-running is a safe no-op — every DDL
-- statement uses an IF (NOT) EXISTS guard. Per ADR-015 D7.
--
-- Verdict-style CHECK constraints are deliberately omitted on `status`
-- and the `sync_type` discriminator, matching the precedent from
-- 20260517_create_fix_runs.sql and 20260518_create_phase3_tables.sql.
--
-- References:
--   * ADR-058 — Phase 4 /census + /sync + /daemon (this migration)
--   * ADR-057 — Phase 3 resource pattern
--   * ADR-055 — fix_runs discriminator precedent
--   * ADR-053 — API as governance interface (parent)
--   * ADR-014 — dev-phase priority; `write` flag honors dry-run-first

BEGIN;

-- ----------------------------------------------------------------------
-- 1. core.census_runs (ADR-058 D1)
--
-- One row per POST /census/runs request. `snapshot` toggles whether the
-- run is a baseline-creation candidate; `baseline_name` is populated
-- when a subsequent POST /census/baselines/{name} promotes this run.
-- The `result` jsonb carries the RepoCensus artifact produced by
-- body.services.cim.CensusService.run_census.
-- ----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS core.census_runs (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    snapshot        BOOLEAN NOT NULL DEFAULT false,
    baseline_name   TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    requested_by    TEXT NOT NULL,
    requested_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    started_at      TIMESTAMP WITH TIME ZONE,
    finished_at     TIMESTAMP WITH TIME ZONE,
    result          JSONB,
    error           TEXT,
    CONSTRAINT census_runs_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS census_runs_requested_at_idx
    ON core.census_runs (requested_at DESC);

CREATE INDEX IF NOT EXISTS census_runs_status_idx
    ON core.census_runs (status);

CREATE INDEX IF NOT EXISTS census_runs_baseline_name_idx
    ON core.census_runs (baseline_name)
 WHERE baseline_name IS NOT NULL;

-- ----------------------------------------------------------------------
-- 2. core.sync_runs (ADR-058 D2)
--
-- One row per POST /sync/{db-registry,vectors,code-vectors,dev-sync}
-- request. `sync_type` is the discriminator (db_registry | vectors |
-- code_vectors | dev_sync). `target` is an optional scope filter
-- forwarded to the backend. `result` jsonb carries counts and changed
-- items; for sync_type='dev_sync' it includes per-phase outcomes.
-- ----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS core.sync_runs (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    sync_type       TEXT NOT NULL,
    write           BOOLEAN NOT NULL DEFAULT false,
    target          TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    requested_by    TEXT NOT NULL,
    requested_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    started_at      TIMESTAMP WITH TIME ZONE,
    finished_at     TIMESTAMP WITH TIME ZONE,
    result          JSONB,
    error           TEXT,
    CONSTRAINT sync_runs_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS sync_runs_requested_at_idx
    ON core.sync_runs (requested_at DESC);

CREATE INDEX IF NOT EXISTS sync_runs_status_idx
    ON core.sync_runs (status);

CREATE INDEX IF NOT EXISTS sync_runs_sync_type_idx
    ON core.sync_runs (sync_type);

-- ----------------------------------------------------------------------
-- Verification: every column on every table is present.
-- ----------------------------------------------------------------------
SELECT
    table_name,
    count(*) FILTER (WHERE column_name = 'id')              AS has_id,
    count(*) FILTER (WHERE column_name = 'status')          AS has_status,
    count(*) FILTER (WHERE column_name = 'requested_by')    AS has_requested_by,
    count(*) FILTER (WHERE column_name = 'requested_at')    AS has_requested_at,
    count(*) FILTER (WHERE column_name = 'started_at')      AS has_started_at,
    count(*) FILTER (WHERE column_name = 'finished_at')     AS has_finished_at,
    count(*) FILTER (WHERE column_name = 'result')          AS has_result,
    count(*) FILTER (WHERE column_name = 'error')           AS has_error
FROM information_schema.columns
WHERE table_schema = 'core'
  AND table_name IN ('census_runs', 'sync_runs')
GROUP BY table_name
ORDER BY table_name;

COMMIT;
