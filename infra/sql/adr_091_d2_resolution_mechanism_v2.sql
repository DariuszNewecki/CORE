-- ADR-091 D2 Revision B — resolution_mechanism CHECK hotfix
--
-- Hotfix for commit b2887afe (commit 1c, 2026-06-06). The original CHECK
-- shipped in adr_091_d2_resolution_mechanism.sql has a SQL three-valued-
-- logic bug that silently permits NULL resolution_mechanism on
-- entry_type='finding' rows — the exact case it was designed to forbid.
--
-- Bug:
--   For a finding row with NULL resolution_mechanism the original CHECK
--     (entry_type = 'finding' AND resolution_mechanism = ANY(ARRAY['reaudit',...]))
--     OR (entry_type <> 'finding' AND resolution_mechanism IS NULL)
--   evaluates to NULL (branch 1: TRUE AND NULL = NULL; branch 2: FALSE).
--   PostgreSQL CHECK constraints accept NULL (only reject FALSE), so the
--   row is admitted.
--
-- Compounding cause: post_observation in src/shared/workers/base.py wrote
-- entry_type='finding' rows without a resolution_mechanism arg (commit 1c
-- recon missed it because Revision B framed scope around open findings,
-- not terminal-at-creation observations). Eleven loop_hold.sample::*
-- rows accumulated between daemon-up at 07:06 CEST and detection at 07:12.
--
-- Fix (this commit):
--   1. post_observation now passes resolution_mechanism='human' — matches
--      the spec's "no automated closer at all" semantics; observations
--      have no re-readable artifact for a sensor to re-evaluate, so they
--      are correctly barred from awaiting_reaudit. The code fix lands in
--      src/shared/workers/base.py.
--   2. The CHECK gains an explicit IS NOT NULL clause on the finding
--      branch so a NULL row evaluates FALSE rather than NULL, failing
--      the constraint as intended.
--   3. Any NULL-mechanism finding rows that snuck in between the v1
--      migration and this hotfix are backfilled to 'human' (the
--      conservative default that grants no reaudit eligibility).
--
-- Acceptance gate (binary): post-hotfix, SELECT count(*) FROM
-- core.blackboard_entries WHERE entry_type='finding' AND
-- resolution_mechanism IS NULL must return 0, and a subsequent INSERT
-- attempting NULL resolution_mechanism on a finding row must raise
-- CheckViolation.
--
-- Idempotent: re-running this script after a successful first run is a
-- no-op — each statement guards against re-execution via IF EXISTS /
-- WHERE NULL predicates / pg_constraint existence check.

BEGIN;

-- (1) Backfill any finding rows whose mechanism is still NULL.
UPDATE core.blackboard_entries
   SET resolution_mechanism = 'human'
 WHERE entry_type = 'finding'
   AND resolution_mechanism IS NULL;

-- (2) Drop the original CHECK if present.
ALTER TABLE core.blackboard_entries
    DROP CONSTRAINT IF EXISTS blackboard_entry_resolution_mechanism_closed_set;

-- (3) Install the tightened CHECK. The IS NOT NULL clause on the finding
-- branch turns the previously-NULL evaluation into FALSE, so the constraint
-- actually fires on the case it was designed to forbid.
ALTER TABLE core.blackboard_entries
    ADD CONSTRAINT blackboard_entry_resolution_mechanism_closed_set
    CHECK (
        (entry_type = 'finding'
            AND resolution_mechanism IS NOT NULL
            AND resolution_mechanism = ANY (ARRAY['reaudit'::text, 'self_resolve'::text, 'human'::text]))
        OR
        (entry_type <> 'finding'
            AND resolution_mechanism IS NULL)
    );

-- Acceptance gate (binary): must return 0 after this script.
--   SELECT count(*) FROM core.blackboard_entries
--    WHERE entry_type='finding' AND resolution_mechanism IS NULL;

COMMIT;
