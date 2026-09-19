-- 20260518_create_phase3_tables.sql
--
-- Creates the three resource tables backing ADR-057 Phase 3:
--
--   * core.coverage_runs          — POST /coverage/generate (and :batch)
--   * core.refactor_runs          — POST /refactor/autonomous
--   * core.audit_remediation_runs — POST /audit/remediations
--
-- BACKGROUND
--
-- ADR-053 D2 established that governor-direct operations submitted
-- via the API are surfaced as resources rather than fire-and-forget
-- RPCs. Phase 1 (ADR-054) shipped core.audit_runs. Phase 2 (ADR-055)
-- shipped core.fix_runs with a `kind` discriminator. Phase 3 stays
-- domain-scoped: each new stateful capability gets its own table
-- (rather than a single 'phase3_runs' with a discriminator) because
-- the operations are unrelated and a discriminator would only add
-- bookkeeping noise.
--
-- All three tables follow the fix_runs lifecycle pattern
-- (pending → executing → completed | failed) and column conventions:
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
-- and the per-domain discriminators, matching the precedent in
-- 20260517_create_fix_runs.sql.
--
-- References:
--   * ADR-057 — Phase 3 /coverage + /refactor + /inspect (this migration)
--   * ADR-055 — Phase 2 pattern (fix_runs)
--   * ADR-054 — Phase 1 pattern (audit_runs)
--   * ADR-053 — API as governance interface (parent)
--   * ADR-038 — circuit breaker (applies to /refactor/autonomous and
--               /audit/remediations autonomous paths)
--   * ADR-014 — dev-phase priority; `write` flag enforces dry-run-first

BEGIN;

-- ----------------------------------------------------------------------
-- 1. core.coverage_runs (ADR-057 D1)
--
-- One row per POST /coverage/generate or POST /coverage/generate:batch
-- request. `target_file` is populated for single-file generation and
-- NULL for batch. `batch_priority` ∈ {'high','all'} for batch rows and
-- NULL for single-file rows. The `result` jsonb carries the list of
-- generated test paths and per-file outcomes.
-- ----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS core.coverage_runs (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    target_file     TEXT,
    batch_priority  TEXT,
    write           BOOLEAN NOT NULL DEFAULT false,
    status          TEXT NOT NULL DEFAULT 'pending',
    requested_by    TEXT NOT NULL,
    requested_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    started_at      TIMESTAMP WITH TIME ZONE,
    finished_at     TIMESTAMP WITH TIME ZONE,
    result          JSONB,
    error           TEXT,
    CONSTRAINT coverage_runs_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS coverage_runs_requested_at_idx
    ON core.coverage_runs (requested_at DESC);

CREATE INDEX IF NOT EXISTS coverage_runs_status_idx
    ON core.coverage_runs (status);

-- ----------------------------------------------------------------------
-- 2. core.refactor_runs (ADR-057 D2)
--
-- One row per POST /refactor/autonomous request. `goal` is the natural-
-- language goal forwarded to the A3 loop (will.autonomy.autonomous_
-- developer.develop_from_goal). The `result` jsonb holds the set of
-- autonomous_proposals.proposal_id values produced. The proposals
-- table itself is unchanged — refactor_runs records the cycle,
-- autonomous_proposals records the outputs, preserving
-- request-to-output traceability per ADR-057 §rationale.
-- ----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS core.refactor_runs (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    goal            TEXT NOT NULL,
    write           BOOLEAN NOT NULL DEFAULT false,
    status          TEXT NOT NULL DEFAULT 'pending',
    requested_by    TEXT NOT NULL,
    requested_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    started_at      TIMESTAMP WITH TIME ZONE,
    finished_at     TIMESTAMP WITH TIME ZONE,
    result          JSONB,
    error           TEXT,
    CONSTRAINT refactor_runs_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS refactor_runs_requested_at_idx
    ON core.refactor_runs (requested_at DESC);

CREATE INDEX IF NOT EXISTS refactor_runs_status_idx
    ON core.refactor_runs (status);

-- ----------------------------------------------------------------------
-- 3. core.audit_remediation_runs (ADR-057 D4)
--
-- One row per POST /audit/remediations request. `audit_run_id` is the
-- FK back to the core.audit_runs row whose findings are being remediated
-- — separate-resource design from ADR-057 D4 ("audit execution and
-- remediation execution as separate resource records, each with their
-- own lifecycle state"). `mode` is the remediation aggressiveness
-- selector ('safe' | 'medium' | 'all'). The `result` jsonb carries
-- proposal_ids, per-rule counts, and a summary block.
-- ----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS core.audit_remediation_runs (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    audit_run_id    UUID,
    mode            TEXT NOT NULL,
    write           BOOLEAN NOT NULL DEFAULT false,
    status          TEXT NOT NULL DEFAULT 'pending',
    requested_by    TEXT NOT NULL,
    requested_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    started_at      TIMESTAMP WITH TIME ZONE,
    finished_at     TIMESTAMP WITH TIME ZONE,
    result          JSONB,
    error           TEXT,
    CONSTRAINT audit_remediation_runs_pkey PRIMARY KEY (id),
    CONSTRAINT audit_remediation_runs_audit_run_id_fkey
        FOREIGN KEY (audit_run_id) REFERENCES core.audit_runs(run_id)
);

CREATE INDEX IF NOT EXISTS audit_remediation_runs_requested_at_idx
    ON core.audit_remediation_runs (requested_at DESC);

CREATE INDEX IF NOT EXISTS audit_remediation_runs_status_idx
    ON core.audit_remediation_runs (status);

CREATE INDEX IF NOT EXISTS audit_remediation_runs_audit_run_id_idx
    ON core.audit_remediation_runs (audit_run_id);

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
  AND table_name IN ('coverage_runs', 'refactor_runs', 'audit_remediation_runs')
GROUP BY table_name
ORDER BY table_name;

COMMIT;
