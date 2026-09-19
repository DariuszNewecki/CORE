-- 20260428_add_claimed_by_to_autonomous_proposals.sql
-- Adds core.autonomous_proposals.claimed_by — the worker_uuid that claims
-- an approved proposal for execution via ProposalStateManager.mark_executing().
-- Mirrors the proven core.blackboard_entries.claimed_by pattern; the
-- existing execution_started_at column already serves the timestamp role
-- and is not duplicated.
--
-- Forward-only per ADR-015 D7: pre-2026-04-28 rows stay NULL; ALCOA+
-- "Complete" forbids backfilling them with synthesized worker UUIDs.
-- No CHECK constraint: D3 prescribes the column only; there is no NFR
-- demanding non-NULL claimed_by.
--
-- References:
--   ADR-015 D3 (column shape + write site at proposal_state_manager.py)
--   ADR-015 D7 (forward-only enforcement)
--   ADR-016 D1 (model registry as schema authority; this migration brings
--               production into alignment with the AutonomousProposal model)
--   URS §3 Q3.F / Q3.R (read path)

BEGIN;

ALTER TABLE core.autonomous_proposals
    ADD COLUMN claimed_by uuid;

COMMIT;
