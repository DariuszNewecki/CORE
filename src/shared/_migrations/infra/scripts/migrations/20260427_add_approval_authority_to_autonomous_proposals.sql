-- 20260427_add_approval_authority_to_autonomous_proposals.sql
-- Adds core.autonomous_proposals.approval_authority and the structural
-- enforcement of URS NFR.5: status cannot transition to
-- approved/executing/completed without a non-NULL authority.
-- Forward-only per ADR-015 D7: pre-2026-04-27 rows are admitted with
-- NULL authority via a created-at carve-out. The carve-out is one-time;
-- post-cutoff rows are bound by the CHECK without exception.
--
-- References:
--   ADR-015 D2 (column shape + CHECK)
--   ADR-015 D7 (forward-only; one-time carve-out)
--   URS NFR.5 (non-omittable at write path)
--
-- Pre-conditions verified 2026-04-27:
--   * core.autonomous_proposals: 0 rows with
--       created_at >= 2026-04-27 00:00:00+00
--       AND status IN ('approved','executing','completed')
--     (i.e. no row would violate the CHECK once the column is added).
--   * The transaction below re-checks this before structural changes
--     land, so a delta between this verification and apply time aborts
--     cleanly rather than corrupting the table.

BEGIN;

-- 1. Pre-flight guard inside the transaction. If any post-cutoff row
--    is in an approved-family status at apply time, the new CHECK
--    would reject it once the column is added. Abort before any
--    structural change.
DO $$
DECLARE
    violation_count INT;
BEGIN
    SELECT COUNT(*) INTO violation_count
    FROM core.autonomous_proposals
    WHERE created_at >= TIMESTAMPTZ '2026-04-27 00:00:00+00'
      AND status IN ('approved', 'executing', 'completed');
    IF violation_count > 0 THEN
        RAISE EXCEPTION
            'Migration aborted: % rows would violate '
            'approval_authority_required_when_approved CHECK '
            'before column is populated. Resolve those rows '
            'before re-running.', violation_count;
    END IF;
END $$;

-- 2. Add the column. Nullable at the column level; the conditional
--    enforcement lives in the CHECK below. ADR-015 D2 specifies text;
--    the closed set of allowed values is enforced at the application
--    layer (ProposalStateManager.approve).
ALTER TABLE core.autonomous_proposals
    ADD COLUMN approval_authority text;

-- 3. Add the structural NFR.5 enforcement. The carve-out admits the
--    159 historical rows that predate this ADR; ALCOA "Complete"
--    forbids backfilling them with synthesized authority values
--    (ADR-015 D7).
ALTER TABLE core.autonomous_proposals
    ADD CONSTRAINT approval_authority_required_when_approved
    CHECK (
        status NOT IN ('approved', 'executing', 'completed')
        OR approval_authority IS NOT NULL
        OR created_at < TIMESTAMPTZ '2026-04-27 00:00:00+00'
    );

COMMIT;
