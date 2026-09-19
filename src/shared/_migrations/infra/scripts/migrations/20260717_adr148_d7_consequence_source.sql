-- ADR-148 D7: label reconstructed consequence rows so a reaper roll-forward
-- (D4) is distinguishable from a genuine, execution-time-captured record.
-- NULL SHA cannot serve as that marker — capture_git_sha() already returns
-- None fail-soft on the normal execution path, so pre_execution_sha IS NULL
-- already means two different things today. An explicit column is the only
-- disambiguation that doesn't overload an existing, ambiguous signal.
--
-- DEFAULT 'execution' backfill is safe: ADR-150 verified live (2026-07-16,
-- re-verified 2026-07-17) that the D4 reconstruction branch has never fired
-- in production — zero proposals ever reached 'finalizing', zero
-- stuck_finalizing findings were ever posted. Every existing row is
-- genuinely execution-sourced.

BEGIN;

ALTER TABLE core.proposal_consequences
    ADD COLUMN IF NOT EXISTS consequence_source text NOT NULL DEFAULT 'execution';

ALTER TABLE core.proposal_consequences
    DROP CONSTRAINT IF EXISTS proposal_consequences_consequence_source_check;
ALTER TABLE core.proposal_consequences
    ADD CONSTRAINT proposal_consequences_consequence_source_check
    CHECK (consequence_source = ANY (ARRAY['execution'::text, 'reaper_reconstructed'::text]));

COMMENT ON COLUMN core.proposal_consequences.consequence_source IS
    'execution: recorded at execution/finalization time with real evidence. '
    'reaper_reconstructed: ProposalPipelineShopManager.stuck_finalizing roll-forward '
    '(ADR-148 D4) synthesized this row after real evidence was unavailable — '
    'pre/post SHA and changed_files are empty by construction, not by observation.';

COMMIT;
