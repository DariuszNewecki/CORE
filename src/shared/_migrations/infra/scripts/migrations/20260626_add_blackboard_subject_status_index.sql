-- Add composite index on core.blackboard_entries (subject, status).
-- Date: 2026-06-26
--
-- External review finding: the dedup SELECT before every post_observation
-- call was an unindexed sequential scan. The (subject, status) predicate
-- matches the WHERE clause used by BlackboardService.find_existing_entry()
-- and the majority of worker claim queries.

BEGIN;

CREATE INDEX idx_blackboard_subject_status
    ON core.blackboard_entries USING btree (subject, status);

COMMIT;
