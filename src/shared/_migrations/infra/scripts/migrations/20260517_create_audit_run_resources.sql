-- 20260517_create_audit_run_resources.sql
--
-- Creates core.audit_run_resources — the API-facing audit-run resource
-- backing the Phase 1 /audit endpoints (ADR-054 D1).
--
-- BACKGROUND
--
-- The legacy core.audit_runs table (bigint id, passed boolean,
-- started_at/finished_at, violations_found) is owned by the CLI audit
-- command and the workflow_gate check. Its shape is incompatible with
-- the resource model ADR-054 calls for (UUID run_id, three-state
-- verdict, status field for pending/completed/failed, blocking_count
-- separate from total finding_count). Rather than mutate the legacy
-- table in place — which would force coordinated changes across
-- src/cli/logic/log_audit.py, list_audits.py, the workflow_gate
-- check, and the SQLAlchemy AuditRun model — we add a sibling table
-- for the API surface. The two coexist; nothing crosses between them.
--
-- ADR-053/-054 invert the CLI-direct audit invocation: the CLI now
-- speaks to the API, and the API persists each audit run as a
-- resource. `POST /audit/runs` inserts a pending row and returns the
-- run_id; the background task that drives the audit updates the row
-- with the final verdict and counts. `GET /audit/runs/{id}` reads
-- back the row.
--
-- SCHEMA
--
-- audit_run_resources(
--     run_id         UUID         PK   DEFAULT gen_random_uuid(),
--     verdict        TEXT         NOT NULL,   -- PASS | FAIL | DEGRADED
--                                             -- (free text; CHECK
--                                             -- deliberately omitted so
--                                             -- transient 'pending'
--                                             -- placeholder is allowed
--                                             -- while audit is in flight)
--     finding_count  INT          NOT NULL,
--     blocking_count INT          NOT NULL,
--     created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
--     completed_at   TIMESTAMPTZ,            -- NULL while pending
--     status         TEXT         NOT NULL DEFAULT 'pending'
--                                             -- pending | completed | failed
-- );
--
-- FORWARD-ONLY. No rollback. Re-running is a safe no-op — every DDL
-- statement uses an IF (NOT) EXISTS guard. Per ADR-015 D7.
--
-- References:
--   * ADR-054 — Phase 1 /audit + /proposals (this migration)
--   * ADR-053 — API as governance interface (parent)
--   * core.audit_runs — legacy CLI/workflow-gate sibling table (untouched)

BEGIN;

CREATE TABLE IF NOT EXISTS core.audit_run_resources (
    run_id         UUID NOT NULL DEFAULT gen_random_uuid(),
    verdict        TEXT NOT NULL,
    finding_count  INT  NOT NULL,
    blocking_count INT  NOT NULL,
    created_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    completed_at   TIMESTAMP WITH TIME ZONE,
    status         TEXT NOT NULL DEFAULT 'pending',
    CONSTRAINT audit_run_resources_pkey PRIMARY KEY (run_id)
);

CREATE INDEX IF NOT EXISTS audit_run_resources_created_at_idx
    ON core.audit_run_resources (created_at DESC);

CREATE INDEX IF NOT EXISTS audit_run_resources_status_idx
    ON core.audit_run_resources (status);

-- Verification: structure is as declared.
SELECT
    count(*) FILTER (WHERE column_name = 'run_id')         AS has_run_id,
    count(*) FILTER (WHERE column_name = 'verdict')        AS has_verdict,
    count(*) FILTER (WHERE column_name = 'finding_count')  AS has_finding_count,
    count(*) FILTER (WHERE column_name = 'blocking_count') AS has_blocking_count,
    count(*) FILTER (WHERE column_name = 'created_at')     AS has_created_at,
    count(*) FILTER (WHERE column_name = 'completed_at')   AS has_completed_at,
    count(*) FILTER (WHERE column_name = 'status')         AS has_status
FROM information_schema.columns
WHERE table_schema = 'core'
  AND table_name = 'audit_run_resources';

COMMIT;
