-- ADR-068: Principal Role Taxonomy
-- Retires human.cli_operator, replaces with principal.governor.
-- Date: 2026-05-22

BEGIN;

-- 1. Backfill: rename all existing human.cli_operator rows
UPDATE core.autonomous_proposals
SET approval_authority = 'principal.governor'
WHERE approval_authority = 'human.cli_operator';

-- Report backfill count
DO $$
DECLARE
    affected INTEGER;
BEGIN
    GET DIAGNOSTICS affected = ROW_COUNT;
    RAISE NOTICE 'ADR-068 backfill: % rows updated from human.cli_operator to principal.governor', affected;
END $$;

-- 2. Add value-restricting CHECK constraint.
-- No existing value-restricting CHECK to drop — ADR-068 introduces this
-- constraint for the first time. The pre-existing
-- approval_authority_required_when_approved CHECK enforces presence-when-
-- approved and is left intact.
ALTER TABLE core.autonomous_proposals
    ADD CONSTRAINT autonomous_proposals_approval_authority_value_check
    CHECK (
        approval_authority IS NULL
        OR approval_authority IN (
            'risk_classification.safe_auto_approval',
            'principal.governor'
        )
    );

-- 3. Verify: no rows carry the retired value
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM core.autonomous_proposals
        WHERE approval_authority = 'human.cli_operator'
    ) THEN
        RAISE EXCEPTION 'ADR-068 migration failed: human.cli_operator rows still present';
    END IF;
    RAISE NOTICE 'ADR-068 migration: verification passed — no human.cli_operator rows remain';
END $$;

COMMIT;
