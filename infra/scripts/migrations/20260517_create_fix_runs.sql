-- 20260517_create_fix_runs.sql
--
-- Creates core.fix_runs — the resource table backing the ADR-055
-- Phase 2 /fix and async /quality endpoints.
--
-- BACKGROUND
--
-- ADR-053 D2 established that governor-direct operations submitted
-- via the API are surfaced as resources rather than fire-and-forget
-- RPCs. ADR-054 implemented this for /audit (core.audit_runs).
-- ADR-055 extends the pattern to fix operations.
--
-- A single fix_runs table backs four `kind` values:
--   * atomic       — POST /fix/run/{fix_id} (ActionExecutor)
--   * flow         — POST /fix/all          (FlowExecutor on flow.fix_code)
--   * modularity   — POST /fix/modularity   (will.workflows modularity path)
--   * quality_check — async /quality/* endpoints (lint, tests, gates, system)
--
-- One table with a `kind` discriminator (instead of one table per
-- subsystem) keeps the resource model uniform and avoids the audit-runs
-- duplication problem ADR-054 fell into during Phase 1.
--
-- SCHEMA (ADR-055 D1)
--
-- fix_runs(
--     id           UUID         PK   DEFAULT gen_random_uuid(),
--     kind         TEXT         NOT NULL,   -- atomic | flow | modularity | ir | quality_check
--     fix_id       TEXT,                    -- action_id or flow_id; NULL for 'all'
--     target_files JSONB,                   -- NULL = repo-wide
--     write        BOOLEAN      NOT NULL,
--     status       TEXT         NOT NULL,   -- pending | executing | completed | failed
--     requested_by TEXT         NOT NULL,
--     requested_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
--     started_at   TIMESTAMPTZ,
--     finished_at  TIMESTAMPTZ,
--     result       JSONB,
--     error        TEXT
-- );
--
-- Verdict-style CHECK constraints are deliberately omitted on `kind`
-- and `status` so the schema does not need migration each time a new
-- kind is wired (`ir` was already added during ADR-055 review). This
-- mirrors the decision in 20260517_create_audit_run_resources.sql to
-- keep `verdict` unconstrained while the surface stabilises.
--
-- FORWARD-ONLY. No rollback. Re-running is a safe no-op — every DDL
-- statement uses an IF (NOT) EXISTS guard. Per ADR-015 D7.
--
-- References:
--   * ADR-055 — Phase 2 /fix + /quality (this migration)
--   * ADR-054 — Phase 1 pattern (audit_runs as resource template)
--   * ADR-053 — API as governance interface (parent)

BEGIN;

CREATE TABLE IF NOT EXISTS core.fix_runs (
    id            UUID NOT NULL DEFAULT gen_random_uuid(),
    kind          TEXT NOT NULL,
    fix_id        TEXT,
    target_files  JSONB,
    write         BOOLEAN NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',
    requested_by  TEXT NOT NULL,
    requested_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    started_at    TIMESTAMP WITH TIME ZONE,
    finished_at   TIMESTAMP WITH TIME ZONE,
    result        JSONB,
    error         TEXT,
    CONSTRAINT fix_runs_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS fix_runs_requested_at_idx
    ON core.fix_runs (requested_at DESC);

CREATE INDEX IF NOT EXISTS fix_runs_status_idx
    ON core.fix_runs (status);

CREATE INDEX IF NOT EXISTS fix_runs_kind_idx
    ON core.fix_runs (kind);

-- Verification: structure is as declared.
SELECT
    count(*) FILTER (WHERE column_name = 'id')           AS has_id,
    count(*) FILTER (WHERE column_name = 'kind')         AS has_kind,
    count(*) FILTER (WHERE column_name = 'fix_id')       AS has_fix_id,
    count(*) FILTER (WHERE column_name = 'target_files') AS has_target_files,
    count(*) FILTER (WHERE column_name = 'write')        AS has_write,
    count(*) FILTER (WHERE column_name = 'status')       AS has_status,
    count(*) FILTER (WHERE column_name = 'requested_by') AS has_requested_by,
    count(*) FILTER (WHERE column_name = 'requested_at') AS has_requested_at,
    count(*) FILTER (WHERE column_name = 'started_at')   AS has_started_at,
    count(*) FILTER (WHERE column_name = 'finished_at')  AS has_finished_at,
    count(*) FILTER (WHERE column_name = 'result')       AS has_result,
    count(*) FILTER (WHERE column_name = 'error')        AS has_error
FROM information_schema.columns
WHERE table_schema = 'core'
  AND table_name = 'fix_runs';

COMMIT;
