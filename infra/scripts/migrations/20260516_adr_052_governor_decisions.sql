-- 20260516_adr_052_governor_decisions.sql
--
-- Governor decisions resolving residual rows after Phase 2 of ADR-052.
-- Applied against the live DB on 2026-05-16. Forward-only, idempotent.
--
-- After Phase 2 (commit 8398483e) `config_migration_log` carried 23 rows
-- with `migrated_at IS NULL`. The governor reviewed the list and issued
-- five named decisions (A–E). This migration implements the three that
-- touch the database (A, B, C); decision D is a no-op; decision E opens
-- a follow-up GitHub issue tracked outside SQL.
--
-- ============================================================
-- DECISION A — llm_connect.timeout, llm_seconds_between.requests
-- ============================================================
-- Both keys were empty values. Per-resource rate limiting now lives on
-- `llm_resources.rate_limit_seconds`; these system-level rate-limit
-- placeholders have no surviving destination column of their own.
-- Mark migrated with destination = llm_resources.rate_limit_seconds so
-- the audit trail records the consolidation.

UPDATE core.config_migration_log
SET migrated_at = now(),
    migrated_by = 'governor-decision-@2',
    destination_table = 'llm_resources',
    destination_column = 'rate_limit_seconds'
WHERE env_key IN ('llm_connect.timeout', 'llm_seconds_between.requests')
  AND migrated_at IS NULL;

-- ============================================================
-- DECISION B — DEEPSEEK_CHAT_API_KEY (legacy uppercase duplicate)
-- ============================================================
-- The canonical `deepseek_chat.api_key` row was migrated to
-- `secret_store` in Phase 2. The uppercase legacy duplicate violates
-- the secret-store naming convention (lowercase, dot-separated) and
-- is retired rather than carried forward.

UPDATE core.config_migration_log
SET migrated_at = now(),
    migrated_by = 'governor-decision-@4',
    destination_table = 'retired',
    destination_column = 'retired'
WHERE env_key = 'DEEPSEEK_CHAT_API_KEY'
  AND migrated_at IS NULL;

-- ============================================================
-- DECISION C — mark 5 unconfigured ollama resources unavailable
-- ============================================================
-- These resources appear in the llm_resources registry but have no
-- entries in runtime_settings for api_url, model_name, or
-- concurrency. Phase 3 will add NOT NULL on model_name; flagging
-- them now lets the audit pipeline surface them as residual config
-- debt without breaking the constraint when Phase 3 lands.
--
-- performance_metadata is jsonb; merge a marker note into whatever
-- is already there (empty in all five cases today, but the merge
-- form is safe regardless).

UPDATE core.llm_resources
SET is_available = false,
    performance_metadata = COALESCE(performance_metadata, '{}'::jsonb)
                           || '{"note": "unconfigured — review required"}'::jsonb
WHERE name IN (
    'ollama_deepseek_coder',
    'ollama_gemma_fast',
    'ollama_llava_vision',
    'ollama_phi3_reasoner',
    'ollama_qwen_general_7b'
)
AND (
    is_available IS DISTINCT FROM false
    OR COALESCE(performance_metadata->>'note', '') <> 'unconfigured — review required'
);

-- ============================================================
-- DECISION D — core.crypto.master_key stays in runtime_settings
-- ============================================================
-- No-op. The crypto master key has a different lifecycle from
-- per-resource credentials and is not migrated to secret_store.
-- This is recorded as a no-op step solely so the file is a
-- complete record of the decision set.

-- ============================================================
-- Verification
-- ============================================================

SELECT
    (SELECT count(*) FROM core.config_migration_log
        WHERE migrated_at IS NULL)                              AS cml_pending,
    (SELECT count(*) FROM core.config_migration_log
        WHERE migrated_by = 'governor-decision-@2')             AS dec_a_marked,
    (SELECT count(*) FROM core.config_migration_log
        WHERE migrated_by = 'governor-decision-@4')             AS dec_b_marked,
    (SELECT count(*) FROM core.llm_resources
        WHERE is_available = false
          AND name IN ('ollama_deepseek_coder','ollama_gemma_fast',
                       'ollama_llava_vision','ollama_phi3_reasoner',
                       'ollama_qwen_general_7b'))               AS dec_c_unavailable,
    (SELECT count(*) FROM core.llm_resources
        WHERE performance_metadata->>'note' = 'unconfigured — review required') AS dec_c_noted;
