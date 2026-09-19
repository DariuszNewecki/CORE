-- #885 -- retire the 'draft' Proposal lifecycle state.
-- DRAFT had no governed semantic function: nothing ever promoted a Proposal
-- out of it, the approval queue listed only 'pending', yet approve()/reject()
-- acted on it directly -- an actionable-but-undiscoverable state. Every
-- creation site now starts in 'pending' (Governor resolution on #885; no ADR).
--
-- Data: existing 'draft' rows become 'pending' -- the state they were always
-- meant to be discoverable in. They surface in the approval queue for the
-- governor to approve or reject; nothing is auto-approved here.
-- Idempotent and transactional. Companion to the ORM/schema.sql change in the
-- same commit; the manifest ledger applies it (core-admin db migrate --apply).

BEGIN;

UPDATE core.autonomous_proposals
    SET status = 'pending',
        updated_at = now()
    WHERE status = 'draft';

ALTER TABLE core.autonomous_proposals
    DROP CONSTRAINT IF EXISTS autonomous_proposals_status_check;
ALTER TABLE core.autonomous_proposals
    ADD CONSTRAINT autonomous_proposals_status_check
    CHECK (status = ANY (ARRAY[
        'pending'::text, 'approved'::text, 'executing'::text,
        'finalizing'::text, 'completed'::text, 'failed'::text, 'rejected'::text]));

ALTER TABLE core.autonomous_proposals
    ALTER COLUMN status SET DEFAULT 'pending'::text;

COMMENT ON COLUMN core.autonomous_proposals.status IS
    'Lifecycle: pending->approved->executing->finalizing->completed/failed/rejected (#885: draft retired)';

COMMIT;
