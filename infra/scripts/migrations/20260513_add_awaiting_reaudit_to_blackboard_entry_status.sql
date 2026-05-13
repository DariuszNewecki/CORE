-- 20260513_add_awaiting_reaudit_to_blackboard_entry_status.sql
-- Adds 'awaiting_reaudit' to the canonical lifecycle states for
-- core.blackboard_entries.status. Companion to ADR-045, which introduces
-- a third state category (non-terminal, non-claimable) that gates the
-- ViolationRemediator's claim queue against stale finding payloads after
-- §7a revival.
--
-- Lifecycle role:
--   awaiting_reaudit — non-terminal, non-claimable. Findings transition
--                      INTO this state from 'deferred_to_proposal' on §7a
--                      revival (governor rejection or automatic
--                      proposal-failure revival). AuditViolationSensor
--                      transitions findings OUT of this state on its next
--                      cycle: to 'open' if the underlying violation still
--                      holds, or to 'resolved' if it has cleared.
--                      resolved_at is NULL while in this state (the row
--                      is active, not terminal).
--
-- Structural state (verified 2026-05-13):
--   * core.blackboard_entries.status is a plain text column constrained
--     by the CHECK constraint 'blackboard_entry_status_closed_set'
--     (installed 2026-05-10 alongside the 'suppressed' addition).
--   * Existing status values: open, claimed, resolved, abandoned,
--     deferred_to_proposal, indeterminate (6 distinct values across
--     ~52K rows; 'awaiting_reaudit' has zero rows today, this migration
--     admits the value so future writes from the revised revival path
--     succeed).
--   * .intent/META/enums.json governance enum 'blackboard_entry_status'
--     updated in lockstep with this migration to include the new value
--     and the three-category description (ADR-045 enum-update artifact
--     at var/adr-drafts/ADR-045-enums.json).
--
-- This migration drops and re-installs the structural CHECK with
-- 'awaiting_reaudit' added. Idempotent (drops first if a prior version
-- exists). Forward-only per ADR-015 D7: only post-migration writes are
-- bound by the new CHECK; the pre-flight guard verifies no current row
-- violates the new constraint before installing it.
--
-- Lock posture (per ADR-045 site 1):
--   ADD CONSTRAINT ... NOT VALID admits the new constraint without a
--   full-table scan, taking ACCESS EXCLUSIVE briefly. The follow-up
--   VALIDATE CONSTRAINT performs the scan under SHARE UPDATE EXCLUSIVE,
--   which permits concurrent reads and DML against the table during the
--   scan. For the current ~52K-row size the scan is sub-second, but the
--   pattern is the right template for future growth.
--
-- References:
--   * ADR-045 (.specs/decisions/ADR-045-quarantine-state-for-revived-findings.md)
--   * 20260510_add_suppressed_to_blackboard_entry_status.sql (precedent)
--   * .intent/META/enums.json — blackboard_entry_status (governor-applied)

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
        'awaiting_reaudit',
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

-- 2. Drop the existing CHECK constraint. Idempotent: tolerates absence
--    so the migration is safe to re-run and to apply in environments
--    where the prior constraint was installed by an earlier closed-set
--    migration.
ALTER TABLE core.blackboard_entries
    DROP CONSTRAINT IF EXISTS blackboard_entry_status_closed_set;

-- 3. Install the new CHECK with NOT VALID so the ADD takes only a brief
--    ACCESS EXCLUSIVE lock without scanning the table. New writes are
--    immediately bound by the constraint; existing rows are validated
--    in step 4 under a weaker lock.
ALTER TABLE core.blackboard_entries
    ADD CONSTRAINT blackboard_entry_status_closed_set
    CHECK (status IN (
        'open',
        'claimed',
        'awaiting_reaudit',
        'resolved',
        'abandoned',
        'deferred_to_proposal',
        'dry_run_complete',
        'indeterminate',
        'suppressed'
    )) NOT VALID;

-- 4. Validate the constraint against existing rows. Takes
--    SHARE UPDATE EXCLUSIVE lock — permits concurrent reads and DML.
--    Pre-flight guard in step 1 guarantees this will succeed.
ALTER TABLE core.blackboard_entries
    VALIDATE CONSTRAINT blackboard_entry_status_closed_set;

COMMIT;
