-- 20260518_consolidate_audit_runs.sql
--
-- Folds core.audit_run_resources into core.audit_runs. After this
-- migration there is a single canonical audit-run table whose shape
-- serves both the legacy CLI/workflow-gate consumers and the
-- ADR-054 /audit HTTP surface.
--
-- BACKGROUND
--
-- 20260517_create_audit_run_resources.sql created a sibling table
-- (core.audit_run_resources) for the API path because the legacy
-- audit_runs shape (BIGINT id, boolean passed, started_at/finished_at,
-- violations_found) was incompatible with the resource model
-- ADR-054 calls for (UUID run_id, tri-state verdict, lifecycle status,
-- separate blocking_count). The two tables coexisted with the
-- understanding that the duplication was temporary.
--
-- This migration removes the duplication. The canonical name stays
-- audit_runs (five existing consumers reference it; only two reference
-- audit_run_resources). The canonical shape adopts the resource
-- vocabulary from audit_run_resources while preserving the provenance
-- columns audit_runs uniquely carries (source, commit_sha, score).
--
-- FINAL SHAPE
--
-- audit_runs(
--     run_id          UUID         PK   DEFAULT gen_random_uuid(),
--     source          TEXT         NOT NULL DEFAULT 'manual',
--                                        -- manual | pr | nightly | api
--     commit_sha      CHAR(40),
--     verdict         TEXT         NOT NULL DEFAULT 'pending',
--                                        -- pending | PASS | FAIL | DEGRADED
--     status          TEXT         NOT NULL DEFAULT 'pending',
--                                        -- pending | completed | failed
--     score           NUMERIC(4,3),
--     finding_count   INT          NOT NULL DEFAULT 0,
--     blocking_count  INT          NOT NULL DEFAULT 0,
--     started_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
--     finished_at     TIMESTAMPTZ
-- )
--
-- The boolean `passed` column is dropped — no external consumer reads
-- it (grep confirmed: only the ORM model and CLI internals, all
-- migrating in the same change-set). No CHECK on verdict so the
-- 'pending' placeholder remains legal, matching the deliberate
-- decision in 20260517_create_audit_run_resources.sql.
--
-- FORWARD-ONLY. No rollback. Per ADR-015 D7.
--
-- References:
--   * ADR-054 — Phase 1 /audit + /proposals
--   * 20260517_create_audit_run_resources.sql — predecessor (removed)

BEGIN;

-- 1. Extend audit_runs with the resource-shape columns.
ALTER TABLE core.audit_runs
    ADD COLUMN IF NOT EXISTS run_id         UUID NOT NULL DEFAULT gen_random_uuid(),
    ADD COLUMN IF NOT EXISTS verdict        TEXT,
    ADD COLUMN IF NOT EXISTS status         TEXT NOT NULL DEFAULT 'completed',
    ADD COLUMN IF NOT EXISTS finding_count  INT  NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS blocking_count INT  NOT NULL DEFAULT 0;

-- 2. Backfill verdict + finding_count from legacy boolean/int semantics.
UPDATE core.audit_runs
   SET verdict       = CASE WHEN passed THEN 'PASS' ELSE 'FAIL' END,
       finding_count = COALESCE(violations_found, 0)
 WHERE verdict IS NULL;

ALTER TABLE core.audit_runs ALTER COLUMN verdict SET NOT NULL;
ALTER TABLE core.audit_runs ALTER COLUMN verdict SET DEFAULT 'pending';

-- 3. Swap PK from id bigint -> run_id uuid. Must happen before the
--    cross-table INSERT below so ON CONFLICT (run_id) has a unique
--    constraint to target. gen_random_uuid() defaults on the existing
--    rows are unique with overwhelming probability — no collision risk.
ALTER TABLE core.audit_runs DROP CONSTRAINT audit_runs_pkey;
ALTER TABLE core.audit_runs ADD CONSTRAINT audit_runs_pkey PRIMARY KEY (run_id);

-- 4. Pull rows from the sibling table into the canonical one.
INSERT INTO core.audit_runs
    (run_id, source, verdict, status, finding_count, blocking_count,
     started_at, finished_at)
SELECT run_id, 'api', verdict, status, finding_count, blocking_count,
       created_at, completed_at
  FROM core.audit_run_resources
 ON CONFLICT (run_id) DO NOTHING;

-- 5. Drop legacy columns + sequence.
ALTER TABLE core.audit_runs
    DROP COLUMN IF EXISTS id,
    DROP COLUMN IF EXISTS passed,
    DROP COLUMN IF EXISTS violations_found;
DROP SEQUENCE IF EXISTS core.audit_runs_id_seq;

-- 6. Replace the legacy 'passed' index with verdict + status indexes.
DROP INDEX IF EXISTS core.idx_audit_runs_passed;
CREATE INDEX IF NOT EXISTS idx_audit_runs_verdict
    ON core.audit_runs (verdict, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_runs_status
    ON core.audit_runs (status);

-- 7. Drop the now-empty sibling.
DROP TABLE IF EXISTS core.audit_run_resources;

-- Verification: canonical column set is present, legacy columns are gone.
SELECT
    count(*) FILTER (WHERE column_name = 'run_id')         AS has_run_id,
    count(*) FILTER (WHERE column_name = 'source')         AS has_source,
    count(*) FILTER (WHERE column_name = 'commit_sha')     AS has_commit_sha,
    count(*) FILTER (WHERE column_name = 'verdict')        AS has_verdict,
    count(*) FILTER (WHERE column_name = 'status')         AS has_status,
    count(*) FILTER (WHERE column_name = 'score')          AS has_score,
    count(*) FILTER (WHERE column_name = 'finding_count')  AS has_finding_count,
    count(*) FILTER (WHERE column_name = 'blocking_count') AS has_blocking_count,
    count(*) FILTER (WHERE column_name = 'started_at')     AS has_started_at,
    count(*) FILTER (WHERE column_name = 'finished_at')    AS has_finished_at,
    count(*) FILTER (WHERE column_name = 'id')             AS leftover_id,
    count(*) FILTER (WHERE column_name = 'passed')         AS leftover_passed,
    count(*) FILTER (WHERE column_name = 'violations_found') AS leftover_violations
FROM information_schema.columns
WHERE table_schema = 'core'
  AND table_name = 'audit_runs';

COMMIT;
