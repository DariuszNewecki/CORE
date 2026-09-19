-- 20260510_add_suppressed_to_blackboard_entry_status.sql
-- Adds 'suppressed' to the canonical lifecycle states for
-- core.blackboard_entries.status. Companion to issue #263, which split
-- the prior single 'abandoned' status into two distinct meanings:
--
--   abandoned  — workers gave up on the entry; the underlying issue is
--                still real, so the sensor that produced this subject
--                is FREE to re-emit on the next detection cycle. No
--                permanent skip semantics.
--   suppressed — governor's deliberate "do not surface this again"
--                signal. The sensor MUST keep skipping this subject
--                permanently. Terminal: resolved_at is set on transition.
--
-- Structural state (verified 2026-05-10):
--   * core.blackboard_entries.status is a plain text column with no
--     PostgreSQL ENUM type backing it and no CHECK constraint enforcing
--     the closed set. The "enum" lives in .intent/META/enums.json
--     (governance-owned) and in application code.
--   * Existing status values are entirely within the canonical set:
--       open, claimed, resolved, abandoned, deferred_to_proposal,
--       dry_run_complete, indeterminate.
--     ('suppressed' has zero rows today; this migration adds the value
--      so future writes are admitted.)
--
-- This migration installs a CHECK constraint enforcing the new closed
-- set including 'suppressed'. The structural CHECK is the closest
-- equivalent to "ALTER TYPE ... ADD VALUE" given the absence of a real
-- PG enum type. Once installed, the DB will reject any string outside
-- the closed set, matching the .intent/META/enums.json contract.
--
-- Forward-only per ADR-015 D7: only post-migration writes are bound by
-- the CHECK; the pre-flight guard verifies that no current row violates
-- the new constraint before installing it.
--
-- References:
--   * Issue #263 (suppressed/abandoned split)
--   * .intent/META/enums.json — blackboard_entry_status (governor-applied)
--   * src/body/services/blackboard_service.py (exclusion lists updated)

BEGIN;

-- 1. Pre-flight guard. If any row carries a status outside the new
--    closed set, abort before the CHECK lands so the structural change
--    cannot orphan rows.
DO $$
DECLARE
    violation_count INT;
BEGIN
    SELECT COUNT(*) INTO violation_count
    FROM core.blackboard_entries
    WHERE status NOT IN (
        'open',
        'claimed',
        'resolved',
        'abandoned',
        'deferred_to_proposal',
        'dry_run_complete',
        'indeterminate',
        'suppressed'
    );
    IF violation_count > 0 THEN
        RAISE EXCEPTION
            'Migration aborted: % rows carry a status outside the '
            'canonical blackboard_entry_status set. Resolve those rows '
            'before re-running.', violation_count;
    END IF;
END $$;

-- 2. Install the CHECK constraint. Drops first if a prior version of
--    this constraint exists, so the migration is idempotent across
--    re-runs and across environments where an earlier closed-set CHECK
--    may already be present under the same name.
ALTER TABLE core.blackboard_entries
    DROP CONSTRAINT IF EXISTS blackboard_entry_status_closed_set;

ALTER TABLE core.blackboard_entries
    ADD CONSTRAINT blackboard_entry_status_closed_set
    CHECK (status IN (
        'open',
        'claimed',
        'resolved',
        'abandoned',
        'deferred_to_proposal',
        'dry_run_complete',
        'indeterminate',
        'suppressed'
    ));

COMMIT;
