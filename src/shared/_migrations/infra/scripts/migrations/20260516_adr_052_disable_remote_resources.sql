-- 20260516_adr_052_disable_remote_resources.sql
--
-- Mark the four external (remote) resources `is_available=false` so the
-- registry state matches `system_config.operating_mode = 'local_only'`.
-- Governor decision following the diagnostic session of 2026-05-16.
--
-- BACKGROUND
--
-- ADR-052 Phase 2 set `llm_resources.locality` per resource (4 remote,
-- 12 local). The system-wide `operating_mode` was set to `local_only`
-- in `system_config`. Today no router code reads either field; the
-- per-resource `is_available` flag is the only governance surface the
-- current router could in principle act on, and even that is not
-- consulted on the autonomous selection path (see issue #N — opened
-- in the same governor decision as this migration).
--
-- Until ADR-052 governing principle #6 is implemented in code,
-- aligning `is_available` with `operating_mode` is the closest thing
-- to enforcement available. Flipping these four to `is_available=false`
-- removes them from the truthful registry surface, regardless of
-- whether the router code chooses to filter on it.
--
-- The change is reversible: setting `is_available=true` re-admits them.
-- Their typed columns (model_name, api_url, locality) and credentials
-- in secret_store remain intact.
--
-- IDEMPOTENCY
--
-- UPDATE gates on `is_available = true`; re-running affects 0 rows.
--
-- References:
--   * ADR-052 — LLM Configuration Domain: Final Schema
--   * ADR-052 governing principle #6 (operating_mode declared in
--     system_config, optionally overridable per role)
--   * 2026-05-16 diagnostic session — surfaced the
--     declaration-vs-enforcement gap.

BEGIN;

UPDATE core.llm_resources
SET is_available = false
WHERE name IN (
    'anthropic_claude_sonnet',
    'deepseek_chat',
    'deepseek_coder',
    'grok'
)
AND is_available = true;

SELECT
    (SELECT count(*) FROM core.llm_resources
        WHERE is_available = true)                  AS available_total,
    (SELECT count(*) FROM core.llm_resources
        WHERE is_available = true  AND locality = 'local')   AS available_local,
    (SELECT count(*) FROM core.llm_resources
        WHERE is_available = true  AND locality = 'remote')  AS available_remote,
    (SELECT count(*) FROM core.llm_resources
        WHERE is_available = false AND locality = 'remote')  AS unavailable_remote;

COMMIT;
