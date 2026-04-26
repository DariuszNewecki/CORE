-- 20260426_drop_legacy_proposals.sql
-- Removes the legacy core.proposals constitutional-replacement proposal surface.
-- Active autonomous proposals live in core.autonomous_proposals (untouched).
--
-- Pre-conditions verified 2026-04-26:
--   * core.proposals: 0 rows
--   * core.proposal_signatures: 0 rows
--   * core.tasks.proposal_id: nullable, never written by A3 pipeline; ORM does
--     not declare it. The two FKs (fk_tasks_proposal, tasks_proposal_id_fkey)
--     and the column itself are dead.

-- 1. Drop FK constraints from core.tasks
ALTER TABLE core.tasks DROP CONSTRAINT IF EXISTS fk_tasks_proposal;
ALTER TABLE core.tasks DROP CONSTRAINT IF EXISTS tasks_proposal_id_fkey;

-- 2. Drop orphaned proposal_id column from core.tasks
ALTER TABLE core.tasks DROP COLUMN IF EXISTS proposal_id;

-- 3. Drop legacy signature table (has FK to proposals, drop first)
DROP TABLE IF EXISTS core.proposal_signatures;

-- 4. Drop legacy proposals table
DROP TABLE IF EXISTS core.proposals;
