-- 20260516_adr_052_retire_orphan_resource_keys.sql
--
-- Closes #331: retire the 8 orphan resource keys surfaced after Phase
-- 2 (commit 8398483e) as unmigrated rows in config_migration_log.
--
-- Investigation summary (per #331 discovery):
--   * No code path in src/ reads any of these keys.
--   * No active cognitive role is assigned to a resource named
--     `local_embedding`, `ollama_local`, or any orphan-prefixed name.
--   * Each value is either an exact duplicate of a value already
--     carried by a registered resource, an empty placeholder, or a
--     defunct alias for a resource now properly named:
--       - local_embedding.{api_url, model_name} → covered by
--         ollama_nomic_embedding.{api_url, model_name}
--       - local_embedding.dim — embedding dimension, no typed home;
--         not load-bearing today.
--       - ollama_local.{api_url, model_name} → covered by
--         ollama_reasoner.{api_url, model_name} (same qwen2.5:7b).
--       - ollama_local_{max_concurrent.requests,
--         seconds_between.requests} — empty placeholders; the named
--         replacement (ollama_reasoner) has populated values.
--       - qwen_local.host — duplicate of qwen_local.api_url
--         (same value on the same llm_resources row).
--
-- Resolution follows the same pattern as decision B in commit
-- 8085c322 (DEEPSEEK_CHAT_API_KEY retirement):
-- destination_table='retired', destination_column='retired',
-- migrated_by='governor-decision-#331'.
--
-- Idempotent. UPDATE gates on `migrated_at IS NULL`; re-running is
-- a safe no-op.
--
-- Verification:
--   * config_migration_log pending count should drop from 20 → 12
--     (the remaining 12 are non-LLM operational settings out of
--     ADR-052 scope).
--
-- References:
--   * Issue #331
--   * Epic #324
--   * ADR-052 — LLM Configuration Domain: Final Schema
--   * Phase 2 commit 8398483e
--   * Governor decisions A–E commit 8085c322 (pattern for decision B)
--   * Phase 3 commit 933c5fe0

BEGIN;

UPDATE core.config_migration_log
SET migrated_at = now(),
    migrated_by = 'governor-decision-#331',
    destination_table = 'retired',
    destination_column = 'retired'
WHERE env_key IN (
    'local_embedding.api_url',
    'local_embedding.dim',
    'local_embedding.model_name',
    'ollama_local.api_url',
    'ollama_local.model_name',
    'ollama_local_max_concurrent.requests',
    'ollama_local_seconds_between.requests',
    'qwen_local.host'
)
AND migrated_at IS NULL;

SELECT
    (SELECT count(*) FROM core.config_migration_log
        WHERE migrated_at IS NULL)                                  AS cml_pending,
    (SELECT count(*) FROM core.config_migration_log
        WHERE migrated_by = 'governor-decision-#331')               AS retired_orphans;

COMMIT;
