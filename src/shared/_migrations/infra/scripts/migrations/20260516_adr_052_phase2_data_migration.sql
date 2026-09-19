-- 20260516_adr_052_phase2_data_migration.sql
--
-- Phase 2 of ADR-052 — data migration from `runtime_settings` to the
-- typed tables created in Phase 1 (commit a6c5fd35).
--
-- No schema changes. No enforcement (Phase 3 lands NOT NULL on
-- llm_resources.model_name and drops cognitive_roles.assigned_resource).
-- ConfigService continues to read from `runtime_settings`; its cutover
-- is data-driven via `is_migration_complete()` which inspects
-- `core.config_migration_log` for any row still carrying
-- `migrated_at IS NULL`.
--
-- BACKGROUND
--
-- Phase 1 populated `core.config_migration_log` with one row per
-- existing `core.runtime_settings` entry (67 rows) and seeded their
-- destination columns to 'pending'. This migration moves the values
-- to their typed homes, updates the log with the real destination,
-- and stamps `migrated_at`.
--
-- A row is considered "mapped" in this phase if:
--   * Its env_key starts with `lower(<env_prefix>)` for some active
--     `llm_resources` row, with a recognised suffix (.api_url,
--     .model_name, .api_key, .max_concurrent / _max_concurrent.requests,
--     .rate_limit / _seconds_between.requests); OR
--   * It is a known system-wide key
--     (LLM_ENABLED / llm.enabled / system.llm_enabled,
--      llm_request.timeout, embed_model.revision).
--
-- Unmapped rows include:
--   * Non-LLM operational settings (paths, log levels, DB URL, etc.)
--   * Orphans with no corresponding llm_resources entry
--     (ollama_local.*, local_embedding.*)
--   * Legacy duplicates (DEEPSEEK_CHAT_API_KEY)
--   * Empty system flags (llm_connect.timeout,
--     llm_seconds_between.requests) with no destination column.
--
-- These remain with `migrated_at IS NULL`. They are surfaced for
-- governor review before Phase 4 (the runtime_settings drop) is
-- permitted.
--
-- IDEMPOTENCY
--
-- Forward-only. Re-running is a safe no-op:
--   * UPDATEs of typed columns gate on the destination cml row still
--     having `migrated_at IS NULL`.
--   * Inserts into secret_store use `ON CONFLICT (key) DO NOTHING`.
--   * Insert into system_config is gated by `NOT EXISTS (SELECT 1
--     FROM system_config)` — the singleton-table contract.
--   * Inserts into role_resource_assignments use
--     `ON CONFLICT (role, resource) DO NOTHING`.
--   * llm_resources.locality is derived deterministically from
--     env_prefix; re-running writes the same value.
--   * config_migration_log destination updates only flip rows
--     whose `migrated_at IS NULL`.
--
-- VERIFICATION
--
-- The trailing SELECT reports:
--   * Per-destination migrated counts (llm_resources.*, secret_store,
--     system_config, role_resource_assignments).
--   * Total config_migration_log rows still pending.
--
-- References:
--   * ADR-052 — LLM Configuration Domain: Final Schema
--   * Issue #326 — Phase 2 tracking issue
--   * Epic #324 — full migration plan
--   * 20260516_adr_052_phase1_llm_config_schema.sql — Phase 1
--     (commit a6c5fd35; creates the destination tables and seeds cml).

BEGIN;

-- =========================================================================
-- 1. llm_resources.locality — derived from env_prefix.
-- =========================================================================
-- The four external providers in the registry are 'remote'; everything
-- else (ollama_*, qwen_local, *_local*) is 'local'. The set is explicit
-- so adding a new external provider requires a deliberate registry
-- update rather than a name-prefix accident.

UPDATE core.llm_resources
SET locality = CASE
    WHEN env_prefix IN (
        'ANTHROPIC_CLAUDE_SONNET',
        'DEEPSEEK_CHAT',
        'DEEPSEEK_CODER',
        'grok'
    ) THEN 'remote'
    ELSE 'local'
END
WHERE locality IS DISTINCT FROM CASE
    WHEN env_prefix IN (
        'ANTHROPIC_CLAUDE_SONNET',
        'DEEPSEEK_CHAT',
        'DEEPSEEK_CODER',
        'grok'
    ) THEN 'remote'
    ELSE 'local'
END;

-- =========================================================================
-- 2. llm_resources.api_url ← runtime_settings.<env_prefix>.api_url
-- =========================================================================

UPDATE core.llm_resources lr
SET api_url = rs.value
FROM core.runtime_settings rs
JOIN core.config_migration_log cml ON cml.env_key = rs.key
WHERE lower(rs.key) = lower(lr.env_prefix) || '.api_url'
  AND rs.value IS NOT NULL
  AND rs.value <> ''
  AND cml.migrated_at IS NULL;

-- =========================================================================
-- 3. llm_resources.model_name ← runtime_settings.<env_prefix>.model_name
-- =========================================================================

UPDATE core.llm_resources lr
SET model_name = rs.value
FROM core.runtime_settings rs
JOIN core.config_migration_log cml ON cml.env_key = rs.key
WHERE lower(rs.key) = lower(lr.env_prefix) || '.model_name'
  AND rs.value IS NOT NULL
  AND rs.value <> ''
  AND cml.migrated_at IS NULL;

-- =========================================================================
-- 4. llm_resources.max_concurrent ← either naming convention.
-- =========================================================================

UPDATE core.llm_resources lr
SET max_concurrent = rs.value::integer
FROM core.runtime_settings rs
JOIN core.config_migration_log cml ON cml.env_key = rs.key
WHERE (lower(rs.key) = lower(lr.env_prefix) || '_max_concurrent.requests'
       OR lower(rs.key) = lower(lr.env_prefix) || '.max_concurrent')
  AND rs.value ~ '^[0-9]+$'
  AND cml.migrated_at IS NULL;

-- =========================================================================
-- 5. llm_resources.rate_limit_seconds ← either naming convention.
-- =========================================================================

UPDATE core.llm_resources lr
SET rate_limit_seconds = rs.value::integer
FROM core.runtime_settings rs
JOIN core.config_migration_log cml ON cml.env_key = rs.key
WHERE (lower(rs.key) = lower(lr.env_prefix) || '_seconds_between.requests'
       OR lower(rs.key) = lower(lr.env_prefix) || '.rate_limit')
  AND rs.value ~ '^[0-9]+$'
  AND cml.migrated_at IS NULL;

-- =========================================================================
-- 6. secret_store ← every <env_prefix>.api_key with a matching resource.
-- =========================================================================
-- The original runtime_settings key is reused verbatim (preserves the
-- existing ConfigService lookup contract). resource_name is the
-- canonical llm_resources.name so "list all credentials for resource X"
-- works without parsing the key string.

INSERT INTO core.secret_store (key, resource_name, value, created_at)
SELECT
    rs.key,
    lr.name,
    rs.value,
    rs.last_updated
FROM core.runtime_settings rs
JOIN core.llm_resources lr ON lower(rs.key) = lower(lr.env_prefix) || '.api_key'
WHERE rs.is_secret = true
  AND rs.value IS NOT NULL
  AND rs.value <> ''
ON CONFLICT (key) DO NOTHING;

-- =========================================================================
-- 7. system_config — typed singleton row from the system-wide flags.
-- =========================================================================
-- Inserts exactly one row if the table is empty. The three duplicate
-- llm_enabled keys collapse to a single boolean (lowercase 'true' wins
-- if all three agree, which they currently do). request_timeout_seconds
-- and embed_model_revision pick up their named keys when present.

INSERT INTO core.system_config (
    operating_mode,
    llm_enabled,
    request_timeout_seconds,
    embed_model_revision
)
SELECT
    'local_only',
    bool_or(
        rs.key IN ('LLM_ENABLED', 'llm.enabled', 'system.llm_enabled')
        AND lower(rs.value) = 'true'
    ),
    COALESCE(
        max(CASE WHEN rs.key = 'llm_request.timeout'
                  AND rs.value ~ '^[0-9]+$'
                 THEN rs.value::integer END),
        300
    ),
    max(CASE WHEN rs.key = 'embed_model.revision' THEN rs.value END)
FROM core.runtime_settings rs
WHERE NOT EXISTS (SELECT 1 FROM core.system_config);

-- =========================================================================
-- 8. role_resource_assignments ← cognitive_roles.assigned_resource.
-- =========================================================================
-- Every current role with a non-null assigned_resource lands as
-- priority=1, is_active=true. Phase 3 drops assigned_resource once
-- code stops reading it; the join row keeps the assignment intact.

INSERT INTO core.role_resource_assignments (role, resource, priority, is_active)
SELECT role, assigned_resource, 1, true
FROM core.cognitive_roles
WHERE assigned_resource IS NOT NULL
ON CONFLICT (role, resource) DO NOTHING;

-- =========================================================================
-- 9. config_migration_log — stamp migrated_at + real destination.
-- =========================================================================
-- Computes the destination per env_key. Only flips rows whose
-- destination is recognised; orphans / non-LLM settings stay with
-- `migrated_at IS NULL` for governor review.

WITH mapped AS (
    SELECT
        rs.key AS env_key,
        CASE
            WHEN rs.key IN ('LLM_ENABLED', 'llm.enabled', 'system.llm_enabled')
                 THEN 'system_config'
            WHEN rs.key = 'llm_request.timeout' THEN 'system_config'
            WHEN rs.key = 'embed_model.revision' THEN 'system_config'
            WHEN EXISTS (
                SELECT 1 FROM core.llm_resources lr
                WHERE lower(rs.key) = lower(lr.env_prefix) || '.api_url'
            ) THEN 'llm_resources'
            WHEN EXISTS (
                SELECT 1 FROM core.llm_resources lr
                WHERE lower(rs.key) = lower(lr.env_prefix) || '.model_name'
            ) THEN 'llm_resources'
            WHEN EXISTS (
                SELECT 1 FROM core.llm_resources lr
                WHERE lower(rs.key) = lower(lr.env_prefix) || '.api_key'
            ) THEN 'secret_store'
            WHEN EXISTS (
                SELECT 1 FROM core.llm_resources lr
                WHERE lower(rs.key) = lower(lr.env_prefix) || '_max_concurrent.requests'
                   OR lower(rs.key) = lower(lr.env_prefix) || '.max_concurrent'
            ) THEN 'llm_resources'
            WHEN EXISTS (
                SELECT 1 FROM core.llm_resources lr
                WHERE lower(rs.key) = lower(lr.env_prefix) || '_seconds_between.requests'
                   OR lower(rs.key) = lower(lr.env_prefix) || '.rate_limit'
            ) THEN 'llm_resources'
            ELSE NULL
        END AS dest_table,
        CASE
            WHEN rs.key IN ('LLM_ENABLED', 'llm.enabled', 'system.llm_enabled')
                 THEN 'llm_enabled'
            WHEN rs.key = 'llm_request.timeout' THEN 'request_timeout_seconds'
            WHEN rs.key = 'embed_model.revision' THEN 'embed_model_revision'
            WHEN EXISTS (
                SELECT 1 FROM core.llm_resources lr
                WHERE lower(rs.key) = lower(lr.env_prefix) || '.api_url'
            ) THEN 'api_url'
            WHEN EXISTS (
                SELECT 1 FROM core.llm_resources lr
                WHERE lower(rs.key) = lower(lr.env_prefix) || '.model_name'
            ) THEN 'model_name'
            WHEN EXISTS (
                SELECT 1 FROM core.llm_resources lr
                WHERE lower(rs.key) = lower(lr.env_prefix) || '.api_key'
            ) THEN 'value'
            WHEN EXISTS (
                SELECT 1 FROM core.llm_resources lr
                WHERE lower(rs.key) = lower(lr.env_prefix) || '_max_concurrent.requests'
                   OR lower(rs.key) = lower(lr.env_prefix) || '.max_concurrent'
            ) THEN 'max_concurrent'
            WHEN EXISTS (
                SELECT 1 FROM core.llm_resources lr
                WHERE lower(rs.key) = lower(lr.env_prefix) || '_seconds_between.requests'
                   OR lower(rs.key) = lower(lr.env_prefix) || '.rate_limit'
            ) THEN 'rate_limit_seconds'
            ELSE NULL
        END AS dest_column
    FROM core.runtime_settings rs
)
UPDATE core.config_migration_log cml
SET migrated_at = now(),
    migrated_by = '20260516_adr_052_phase2',
    destination_table = mapped.dest_table,
    destination_column = mapped.dest_column
FROM mapped
WHERE cml.env_key = mapped.env_key
  AND cml.migrated_at IS NULL
  AND mapped.dest_table IS NOT NULL;

-- =========================================================================
-- Verification — counts by destination + residual pending count.
-- =========================================================================

SELECT
    -- llm_resources column population
    (SELECT count(*) FROM core.llm_resources WHERE model_name IS NOT NULL) AS llm_resources_with_model_name,
    (SELECT count(*) FROM core.llm_resources WHERE api_url IS NOT NULL)    AS llm_resources_with_api_url,
    (SELECT count(*) FROM core.llm_resources WHERE locality = 'remote')    AS llm_resources_remote,
    (SELECT count(*) FROM core.llm_resources WHERE locality = 'local')     AS llm_resources_local,
    -- secret_store population
    (SELECT count(*) FROM core.secret_store)                               AS secret_store_rows,
    -- system_config (must be 1)
    (SELECT count(*) FROM core.system_config)                              AS system_config_rows,
    -- role_resource_assignments vs source rows
    (SELECT count(*) FROM core.cognitive_roles
        WHERE assigned_resource IS NOT NULL)                               AS cognitive_roles_assigned,
    (SELECT count(*) FROM core.role_resource_assignments
        WHERE priority = 1 AND is_active = true)                           AS role_assignments_priority_1,
    -- cml progress
    (SELECT count(*) FROM core.config_migration_log)                       AS cml_total,
    (SELECT count(*) FROM core.config_migration_log
        WHERE migrated_at IS NOT NULL)                                     AS cml_migrated,
    (SELECT count(*) FROM core.config_migration_log
        WHERE migrated_at IS NULL)                                         AS cml_pending;

COMMIT;
