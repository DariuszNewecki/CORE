-- 20260919c_adr054_audit_findings_run_id.sql
--
-- ADR-162 U5a — historical reconstruction (backfill).
--
-- Origin: ADR-054 Amendment 2026-07-07 (#345, commit 233ebfda): core.audit_findings
-- gains `run_id uuid NOT NULL REFERENCES core.audit_runs(run_id)` plus four
-- indexes, promoting it from a TRUNCATE-and-INSERT scratch table to an
-- append-only historical record; the writer (src/cli/commands/check/audit.py)
-- has inserted run_id since v2.9.1. The change was applied to the live
-- database by hand and captured in schema.sql at 8d02e21b (2026-07-14); no
-- migration file existed.
--
-- Existing rows: before #345 the table held at most the LAST audit run's
-- findings (truncated on every run) and no run association. They are not
-- discarded: they are preserved under one explicitly labelled synthetic
-- audit_runs row (source = 'pre_adr054_scratch_backfill', verdict 'unknown')
-- so the NOT NULL constraint holds without data loss. On a database without
-- orphan rows nothing is synthesised.
--
-- Idempotent; one transaction. Names match the canonical schema.sql exactly.

BEGIN;

ALTER TABLE core.audit_findings
    ADD COLUMN IF NOT EXISTS run_id uuid;

-- Preserve pre-#345 scratch rows under one labelled run (only if any exist).
WITH orphans AS (
    SELECT id, created_at, severity
    FROM core.audit_findings
    WHERE run_id IS NULL
),
synthetic_run AS (
    INSERT INTO core.audit_runs
        (source, verdict, status, finding_count, blocking_count, started_at, finished_at)
    SELECT
        'pre_adr054_scratch_backfill',
        'unknown',
        'completed',
        count(*),
        count(*) FILTER (WHERE severity = 'block'),
        min(created_at),
        max(created_at)
    FROM orphans
    HAVING count(*) > 0
    RETURNING run_id
)
UPDATE core.audit_findings f
SET run_id = synthetic_run.run_id
FROM synthetic_run
WHERE f.run_id IS NULL;

ALTER TABLE core.audit_findings
    ALTER COLUMN run_id SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'core.audit_findings'::regclass
          AND conname = 'audit_findings_run_id_fkey'
    ) THEN
        ALTER TABLE core.audit_findings
            ADD CONSTRAINT audit_findings_run_id_fkey
            FOREIGN KEY (run_id) REFERENCES core.audit_runs(run_id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_audit_findings_run_id
    ON core.audit_findings USING btree (run_id);
CREATE INDEX IF NOT EXISTS idx_audit_findings_run_severity
    ON core.audit_findings USING btree (run_id, severity);
CREATE INDEX IF NOT EXISTS idx_audit_findings_check_run
    ON core.audit_findings USING btree (check_id, run_id);
CREATE INDEX IF NOT EXISTS idx_audit_findings_file_run
    ON core.audit_findings USING btree (file_path, run_id);

COMMIT;
