-- ADR-091 D2 Revision B — resolution_mechanism column migration
--
-- Adds resolution_mechanism to core.blackboard_entries, backfills every
-- existing row by subject-prefix match, then installs the closed-set CHECK.
--
-- Load-bearing invariant (ADR-091 D2):
--   A finding may be transitioned to awaiting_reaudit if and only if its
--   resolution_mechanism = 'reaudit'.
--
-- Order matters. The CHECK requires non-NULL on findings and NULL on every
-- other entry_type; adding the constraint before backfill would reject the
-- live tree. The three statements must run in this order:
--
--   1. ALTER TABLE ADD COLUMN  (nullable, no default — CHECK does the gating)
--   2. UPDATE backfill         (classify every finding row by subject prefix)
--   3. ALTER TABLE ADD CONSTRAINT
--
-- Backfill classification (matches Revision B (e)(7)):
--   - python::%                            -> reaudit       (all artifact findings post-commits 0/1/1b)
--   - worker.silent::%                     -> self_resolve  (worker_shop_manager)
--   - blackboard.entry_stale::%            -> self_resolve  (blackboard_shop_manager → SQL sweep)
--   - proposal.stuck_approved::%           -> self_resolve  (proposal_pipeline_shop_manager)
--   - proposal.stuck_executing::%          -> self_resolve  (proposal_pipeline_shop_manager)
--   - proposal.repeated_failure::%         -> self_resolve  (proposal_pipeline_shop_manager)
--   - everything else (entry_type=finding) -> human         (conservative default; no reaudit eligibility)
--
-- Non-finding rows (report, heartbeat, claim, proposal) stay NULL — the new
-- column is nullable by default and the CHECK requires NULL for them.
--
-- Idempotent: re-running this script after a successful first run is a no-op.
-- Each statement guards against re-execution via IF NOT EXISTS / WHERE NULL
-- predicates / pg_constraint existence check.

BEGIN;

-- (1) Column.
ALTER TABLE core.blackboard_entries
    ADD COLUMN IF NOT EXISTS resolution_mechanism text;

-- (2) Backfill. Only touch finding rows whose mechanism is still NULL.
UPDATE core.blackboard_entries
   SET resolution_mechanism = 'reaudit'
 WHERE entry_type = 'finding'
   AND resolution_mechanism IS NULL
   AND subject LIKE 'python::%';

UPDATE core.blackboard_entries
   SET resolution_mechanism = 'self_resolve'
 WHERE entry_type = 'finding'
   AND resolution_mechanism IS NULL
   AND (
        subject LIKE 'worker.silent::%'
     OR subject LIKE 'blackboard.entry_stale::%'
     OR subject LIKE 'proposal.stuck_approved::%'
     OR subject LIKE 'proposal.stuck_executing::%'
     OR subject LIKE 'proposal.repeated_failure::%'
   );

UPDATE core.blackboard_entries
   SET resolution_mechanism = 'human'
 WHERE entry_type = 'finding'
   AND resolution_mechanism IS NULL;

-- (3) CHECK. Mirror the application-side enum + non-omittable invariant in
-- the same shape as the existing blackboard_entry_status_closed_set
-- (positional CHECK, no NOT VALID), so the contract and the DB cannot drift.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'blackboard_entry_resolution_mechanism_closed_set'
           AND conrelid = 'core.blackboard_entries'::regclass
    ) THEN
        ALTER TABLE core.blackboard_entries
            ADD CONSTRAINT blackboard_entry_resolution_mechanism_closed_set
            CHECK (
                (entry_type = 'finding'
                    AND resolution_mechanism = ANY (ARRAY['reaudit'::text, 'self_resolve'::text, 'human'::text]))
                OR
                (entry_type <> 'finding'
                    AND resolution_mechanism IS NULL)
            );
    END IF;
END
$$;

-- Acceptance gate (binary): must return 0 after this script.
--   SELECT count(*) FROM core.blackboard_entries
--    WHERE entry_type='finding' AND resolution_mechanism IS NULL;

COMMIT;
