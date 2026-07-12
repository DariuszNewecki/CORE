-- ADR-148 (finalization barrier), Stage 2 (D1 + D2).
-- Adds the 'finalizing' lifecycle state and the consequence_recorded_at column
-- to core.autonomous_proposals. Safe against existing data: no 'finalizing'
-- rows exist yet, so the stricter constraints cannot be violated. Idempotent
-- and transactional.

BEGIN;

-- D2: 'finalizing' joins the status vocabulary (post-commit, evidence-recording).
ALTER TABLE core.autonomous_proposals
    DROP CONSTRAINT IF EXISTS autonomous_proposals_status_check;
ALTER TABLE core.autonomous_proposals
    ADD CONSTRAINT autonomous_proposals_status_check
    CHECK (status = ANY (ARRAY[
        'draft'::text, 'pending'::text, 'approved'::text, 'executing'::text,
        'finalizing'::text, 'completed'::text, 'failed'::text, 'rejected'::text]));

-- 'finalizing' is post-approval, so approval_authority is required through it.
ALTER TABLE core.autonomous_proposals
    DROP CONSTRAINT IF EXISTS approval_authority_required_when_approved;
ALTER TABLE core.autonomous_proposals
    ADD CONSTRAINT approval_authority_required_when_approved
    CHECK ((status <> ALL (ARRAY[
        'approved'::text, 'executing'::text, 'finalizing'::text, 'completed'::text]))
        OR (approval_authority IS NOT NULL)
        OR (created_at < '2026-04-27 00:00:00+00'::timestamp with time zone));

-- D1: consequence_recorded_at — proof the consequence chain is durable.
-- Required (non-null) for status='completed' after ADR-148 Stage 2 lands.
ALTER TABLE core.autonomous_proposals
    ADD COLUMN IF NOT EXISTS consequence_recorded_at timestamp with time zone;

COMMENT ON COLUMN core.autonomous_proposals.status IS
    'Lifecycle: draft->pending->approved->executing->finalizing->completed/failed/rejected';

COMMIT;
