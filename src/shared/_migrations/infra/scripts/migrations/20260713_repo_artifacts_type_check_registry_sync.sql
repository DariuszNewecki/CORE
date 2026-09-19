-- Issue #776 / regression of #646-#647: repo_artifacts_type_check drifted
-- out of sync with .intent/artifact_types/*.yaml. 5 registry types added
-- 2026-07-07 (architecture_bridge, charter, northstar, planning, requirement)
-- were never added to the CHECK, so every crawl of their matching files
-- (.intent/architecture/bridges/*.yaml, .specs/CORE-CHARTER.md,
-- .specs/northstar/*.md, .specs/planning/*.md, .specs/requirements/*.md)
-- has been rejected with CheckViolationError (~1504 occurrences/day).
--
-- New set is the full 17-id .intent/artifact_types/ registry (verified via
-- tests/infra/test_repo_artifacts_type_check_matches_registry.py, re-armed
-- in commit 58aa3891 after it silently went dark following #521's
-- infra/sql/db_schema_live.sql -> schema.sql rename). Idempotent and
-- transactional.

BEGIN;

ALTER TABLE core.repo_artifacts
    DROP CONSTRAINT IF EXISTS repo_artifacts_type_check;
ALTER TABLE core.repo_artifacts
    ADD CONSTRAINT repo_artifacts_type_check
    CHECK ((artifact_type = ANY (ARRAY[
        'adr'::text, 'architecture_bridge'::text, 'charter'::text, 'doc'::text,
        'document_corpus'::text, 'infra'::text, 'intent_json'::text,
        'intent_yaml'::text, 'northstar'::text, 'paper'::text, 'planning'::text,
        'prompt'::text, 'python'::text, 'report'::text, 'requirement'::text,
        'spec_markdown'::text, 'test'::text])));

COMMIT;
