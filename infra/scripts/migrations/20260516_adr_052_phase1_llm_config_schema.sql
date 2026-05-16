-- 20260516_adr_052_phase1_llm_config_schema.sql
--
-- Phase 1 of ADR-052 — LLM Configuration Domain: Final Schema.
-- Additive only. No drops. No data moves beyond seeding
-- core.config_migration_log from core.runtime_settings.
--
-- BACKGROUND
--
-- During initial CORE setup, all non-DB configuration lived in `.env`.
-- A decision was made that `.env` must carry only DB connection
-- settings — everything else moves to the database. At that time,
-- destination tables did not yet exist, so `runtime_settings` was
-- introduced as a transitional key-value store: a DB-based copy of
-- `.env` with the same flat, untyped, key=value structure. Proper
-- tables (`llm_resources`, `cognitive_roles`) were subsequently
-- created, but the migration from `runtime_settings` was never
-- completed.
--
-- ADR-052 defines the complete target schema and a four-phase
-- migration. This is Phase 1: create the new tables, add nullable
-- columns to existing tables, add FK constraints to
-- `semantic_cache.cognitive_role` and `agent_memory.cognitive_role`,
-- and seed `config_migration_log` with one row per current
-- `runtime_settings` entry. After this migration, the database
-- carries both the old and new schemas in parallel. Existing readers
-- continue to use `runtime_settings`.
--
-- PHASE 1 SCOPE
--
-- New tables (all in the `core` schema):
--   * role_resource_assignments  — replaces single-FK assigned_resource
--                                  with priority-ordered fallback list
--   * system_config              — typed singleton; collapses the three
--                                  duplicate llm_enabled flags
--   * secret_store               — typed replacement for is_secret=true
--                                  rows in runtime_settings
--   * config_migration_log       — .env → final-table audit trail
--   * capability_alignment_tests — benchmark test suite definitions
--   * model_performance_results  — per-model benchmark scores
--   * llm_exchange_log           — append-only LLM-interaction record,
--                                  partitioned monthly by `ts`
--   * llm_exchange_log_2026_05   — initial monthly partition
--
-- Modified tables (additive only):
--   * llm_resources   — adds model_name, api_url, locality, concurrency,
--                       retry, cost, health, registration columns. All
--                       nullable in Phase 1; NOT NULL on model_name lands
--                       in Phase 3 (after Phase 2 backfills).
--   * cognitive_roles — adds operating_mode (nullable; NULL means inherit
--                       from system_config.operating_mode).
--   * semantic_cache  — adds FK on cognitive_role → cognitive_roles(role).
--   * agent_memory    — adds FK on cognitive_role → cognitive_roles(role).
--
-- Populated:
--   * config_migration_log — one row per current runtime_settings entry.
--     destination_table and destination_column are seeded as 'pending';
--     Phase 2 updates them to the real destinations as each row is
--     copied to its typed home. migrated_at = NULL until Phase 2 lands.
--
-- IDEMPOTENCY
--
-- Forward-only. No rollback. Re-running is a safe no-op:
--   * Every CREATE uses IF NOT EXISTS.
--   * Every ADD COLUMN uses IF NOT EXISTS.
--   * FK constraints are guarded by a constraint-name lookup in
--     information_schema.table_constraints before ALTER TABLE.
--   * config_migration_log is seeded only when empty; re-running
--     after Phase 1 will not duplicate rows.
--
-- VERIFICATION
--
-- The SELECT at the end of the transaction returns one row of
-- presence-counts. Every value should be ≥1 after a successful run.
-- A separate row-count check against runtime_settings is reported
-- alongside the structure check.
--
-- References:
--   * ADR-052 — LLM Configuration Domain: Final Schema
--   * Issue #325 — Phase 1 tracking issue
--   * Epic #324 — full migration plan
--   * 20260513_create_llm_gate_verdicts.sql — precedent for shape

BEGIN;

-- =========================================================================
-- 1. role_resource_assignments — priority-ordered role → resource mapping
-- =========================================================================

CREATE TABLE IF NOT EXISTS core.role_resource_assignments (
    role        TEXT NOT NULL,
    resource    TEXT NOT NULL,
    priority    INTEGER NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT true,
    assigned_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT role_resource_assignments_pkey
        PRIMARY KEY (role, resource),
    CONSTRAINT role_resource_assignments_priority_check
        CHECK (priority >= 1),
    CONSTRAINT role_resource_assignments_role_fkey
        FOREIGN KEY (role) REFERENCES core.cognitive_roles(role)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT role_resource_assignments_resource_fkey
        FOREIGN KEY (resource) REFERENCES core.llm_resources(name)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE UNIQUE INDEX IF NOT EXISTS role_resource_assignments_active_priority_idx
    ON core.role_resource_assignments (role, priority)
    WHERE is_active;

-- =========================================================================
-- 2. system_config — typed singleton for system-wide flags
-- =========================================================================

CREATE TABLE IF NOT EXISTS core.system_config (
    id                      UUID NOT NULL DEFAULT gen_random_uuid(),
    operating_mode          TEXT NOT NULL DEFAULT 'local_only',
    llm_enabled             BOOLEAN NOT NULL DEFAULT true,
    request_timeout_seconds INTEGER NOT NULL DEFAULT 300,
    embed_model_revision    TEXT,
    updated_at              TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT system_config_pkey PRIMARY KEY (id),
    CONSTRAINT system_config_operating_mode_check
        CHECK (operating_mode IN ('local_only', 'remote_only', 'hybrid'))
);

-- =========================================================================
-- 3. secret_store — typed replacement for is_secret=true runtime_settings
-- =========================================================================

CREATE TABLE IF NOT EXISTS core.secret_store (
    key             TEXT NOT NULL,
    resource_name   TEXT,
    value           TEXT NOT NULL,
    last_rotated_at TIMESTAMP WITH TIME ZONE,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT secret_store_pkey PRIMARY KEY (key),
    CONSTRAINT secret_store_resource_name_fkey
        FOREIGN KEY (resource_name) REFERENCES core.llm_resources(name)
        ON UPDATE CASCADE ON DELETE SET NULL
);

-- =========================================================================
-- 4. config_migration_log — .env → final-table audit trail
-- =========================================================================

CREATE TABLE IF NOT EXISTS core.config_migration_log (
    id                 UUID NOT NULL DEFAULT gen_random_uuid(),
    env_key            TEXT NOT NULL,
    source             TEXT NOT NULL,
    destination_table  TEXT NOT NULL,
    destination_column TEXT NOT NULL,
    imported_at        TIMESTAMP WITH TIME ZONE NOT NULL,
    migrated_at        TIMESTAMP WITH TIME ZONE,
    migrated_by        TEXT NOT NULL,
    CONSTRAINT config_migration_log_pkey PRIMARY KEY (id),
    CONSTRAINT config_migration_log_source_check
        CHECK (source IN ('dotenv', 'runtime_settings'))
);

CREATE INDEX IF NOT EXISTS config_migration_log_pending_idx
    ON core.config_migration_log (env_key)
    WHERE migrated_at IS NULL;

-- =========================================================================
-- 5. capability_alignment_tests — benchmark test suite
-- =========================================================================

CREATE TABLE IF NOT EXISTS core.capability_alignment_tests (
    id                UUID NOT NULL DEFAULT gen_random_uuid(),
    name              TEXT NOT NULL,
    capability        TEXT NOT NULL,
    expected_behavior TEXT NOT NULL,
    scoring_rubric    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT capability_alignment_tests_pkey PRIMARY KEY (id),
    CONSTRAINT capability_alignment_tests_name_key UNIQUE (name)
);

-- =========================================================================
-- 6. model_performance_results — per-model benchmark scores
-- =========================================================================

CREATE TABLE IF NOT EXISTS core.model_performance_results (
    id            UUID NOT NULL DEFAULT gen_random_uuid(),
    resource_name TEXT NOT NULL,
    test_id       UUID NOT NULL,
    score         NUMERIC(5, 2) NOT NULL,
    notes         TEXT,
    triggered_by  TEXT NOT NULL,
    evaluated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT model_performance_results_pkey PRIMARY KEY (id),
    CONSTRAINT model_performance_results_score_check
        CHECK (score BETWEEN 0 AND 100),
    CONSTRAINT model_performance_results_triggered_by_check
        CHECK (triggered_by IN ('registration', 'manual', 'scheduled')),
    CONSTRAINT model_performance_results_resource_fkey
        FOREIGN KEY (resource_name) REFERENCES core.llm_resources(name)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT model_performance_results_test_fkey
        FOREIGN KEY (test_id) REFERENCES core.capability_alignment_tests(id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS model_performance_results_resource_evaluated_idx
    ON core.model_performance_results (resource_name, evaluated_at DESC);

-- Deduplication guard: a model may only have one `registration` benchmark
-- per test. Manual and scheduled runs are unrestricted. To re-run a
-- registration benchmark, delete the existing row explicitly.
CREATE UNIQUE INDEX IF NOT EXISTS
    model_performance_results_registration_unique_idx
    ON core.model_performance_results (resource_name, test_id)
    WHERE triggered_by = 'registration';

-- =========================================================================
-- 7. llm_exchange_log — append-only LLM-interaction record (partitioned)
-- =========================================================================

CREATE TABLE IF NOT EXISTS core.llm_exchange_log (
    id                UUID NOT NULL DEFAULT gen_random_uuid(),
    resource_name     TEXT NOT NULL,
    cognitive_role    TEXT NOT NULL,
    task_id           UUID,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    duration_ms       INTEGER,
    model_snapshot    TEXT NOT NULL,
    cost_estimate     NUMERIC(10, 6),
    privacy_level     TEXT NOT NULL DEFAULT 'standard',
    redacted          BOOLEAN NOT NULL DEFAULT false,
    ts                TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT llm_exchange_log_pkey PRIMARY KEY (id, ts),
    CONSTRAINT llm_exchange_log_privacy_check
        CHECK (privacy_level IN ('standard', 'restricted', 'redacted')),
    CONSTRAINT llm_exchange_log_resource_fkey
        FOREIGN KEY (resource_name) REFERENCES core.llm_resources(name)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT llm_exchange_log_role_fkey
        FOREIGN KEY (cognitive_role) REFERENCES core.cognitive_roles(role)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT llm_exchange_log_task_fkey
        FOREIGN KEY (task_id) REFERENCES core.tasks(id) ON DELETE SET NULL
) PARTITION BY RANGE (ts);

-- Initial monthly partition for May 2026. Subsequent months are created
-- ahead of time by the partition-maintenance job tracked in issue #329.
CREATE TABLE IF NOT EXISTS core.llm_exchange_log_2026_05
    PARTITION OF core.llm_exchange_log
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

CREATE INDEX IF NOT EXISTS llm_exchange_log_resource_ts_idx
    ON core.llm_exchange_log (resource_name, ts DESC);

CREATE INDEX IF NOT EXISTS llm_exchange_log_role_ts_idx
    ON core.llm_exchange_log (cognitive_role, ts DESC);

CREATE INDEX IF NOT EXISTS llm_exchange_log_task_idx
    ON core.llm_exchange_log (task_id);

-- =========================================================================
-- 8. llm_resources — additive typed columns. NULL today; Phase 2 backfills.
-- =========================================================================

ALTER TABLE core.llm_resources
    ADD COLUMN IF NOT EXISTS model_name            TEXT,
    ADD COLUMN IF NOT EXISTS api_url               TEXT,
    ADD COLUMN IF NOT EXISTS locality              TEXT NOT NULL DEFAULT 'local',
    ADD COLUMN IF NOT EXISTS max_concurrent        INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS rate_limit_seconds    INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS retry_attempts        INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS retry_backoff_seconds INTEGER NOT NULL DEFAULT 5,
    ADD COLUMN IF NOT EXISTS cost_per_token        NUMERIC(12, 8),
    ADD COLUMN IF NOT EXISTS health_status         TEXT DEFAULT 'unknown',
    ADD COLUMN IF NOT EXISTS last_health_check_at  TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS registered_at         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now();

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_schema = 'core'
          AND table_name = 'llm_resources'
          AND constraint_name = 'llm_resources_locality_check'
    ) THEN
        ALTER TABLE core.llm_resources
            ADD CONSTRAINT llm_resources_locality_check
            CHECK (locality IN ('local', 'remote'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_schema = 'core'
          AND table_name = 'llm_resources'
          AND constraint_name = 'llm_resources_health_status_check'
    ) THEN
        ALTER TABLE core.llm_resources
            ADD CONSTRAINT llm_resources_health_status_check
            CHECK (health_status IS NULL
                   OR health_status IN ('healthy', 'degraded', 'unavailable', 'unknown'));
    END IF;
END
$$;

-- =========================================================================
-- 9. cognitive_roles — additive operating_mode (nullable = inherit system)
-- =========================================================================

ALTER TABLE core.cognitive_roles
    ADD COLUMN IF NOT EXISTS operating_mode TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_schema = 'core'
          AND table_name = 'cognitive_roles'
          AND constraint_name = 'cognitive_roles_operating_mode_check'
    ) THEN
        ALTER TABLE core.cognitive_roles
            ADD CONSTRAINT cognitive_roles_operating_mode_check
            CHECK (operating_mode IS NULL
                   OR operating_mode IN ('local_only', 'remote_only', 'hybrid'));
    END IF;
END
$$;

-- =========================================================================
-- 10. semantic_cache — add FK on cognitive_role
-- =========================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_schema = 'core'
          AND table_name = 'semantic_cache'
          AND constraint_name = 'fk_semantic_cache_cognitive_role'
    ) THEN
        ALTER TABLE core.semantic_cache
            ADD CONSTRAINT fk_semantic_cache_cognitive_role
            FOREIGN KEY (cognitive_role) REFERENCES core.cognitive_roles(role)
            ON UPDATE CASCADE ON DELETE RESTRICT;
    END IF;
END
$$;

-- =========================================================================
-- 11. agent_memory — add FK on cognitive_role
-- =========================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_schema = 'core'
          AND table_name = 'agent_memory'
          AND constraint_name = 'fk_agent_memory_cognitive_role'
    ) THEN
        ALTER TABLE core.agent_memory
            ADD CONSTRAINT fk_agent_memory_cognitive_role
            FOREIGN KEY (cognitive_role) REFERENCES core.cognitive_roles(role)
            ON UPDATE CASCADE ON DELETE RESTRICT;
    END IF;
END
$$;

-- =========================================================================
-- 12. Seed config_migration_log from runtime_settings
-- =========================================================================
--
-- One row per current runtime_settings entry.
-- imported_at = runtime_settings.last_updated.
-- migrated_at = NULL (Phase 2 populates this column when each row is
-- copied to its typed home).
-- destination_table / destination_column = 'pending' — Phase 2 backfills
-- the real destinations as part of the data move.
-- migrated_by = '20260516_adr_052_phase1' — the migration that seeded
-- the row; Phase 2 will overwrite per actor performing the migration.
--
-- Guarded: only seeds when config_migration_log is empty. Re-running
-- after Phase 1 does not duplicate rows.

INSERT INTO core.config_migration_log
    (env_key, source, destination_table, destination_column,
     imported_at, migrated_at, migrated_by)
SELECT
    rs.key,
    'runtime_settings',
    'pending',
    'pending',
    rs.last_updated,
    NULL,
    '20260516_adr_052_phase1'
FROM core.runtime_settings rs
WHERE NOT EXISTS (SELECT 1 FROM core.config_migration_log);

-- =========================================================================
-- Verification — structural presence + populate completeness.
-- =========================================================================

SELECT
    -- New tables present
    (SELECT count(*) FROM information_schema.tables
       WHERE table_schema = 'core'
         AND table_name = 'role_resource_assignments')   AS has_role_resource_assignments,
    (SELECT count(*) FROM information_schema.tables
       WHERE table_schema = 'core'
         AND table_name = 'system_config')               AS has_system_config,
    (SELECT count(*) FROM information_schema.tables
       WHERE table_schema = 'core'
         AND table_name = 'secret_store')                AS has_secret_store,
    (SELECT count(*) FROM information_schema.tables
       WHERE table_schema = 'core'
         AND table_name = 'config_migration_log')        AS has_config_migration_log,
    (SELECT count(*) FROM information_schema.tables
       WHERE table_schema = 'core'
         AND table_name = 'capability_alignment_tests')  AS has_capability_alignment_tests,
    (SELECT count(*) FROM information_schema.tables
       WHERE table_schema = 'core'
         AND table_name = 'model_performance_results')   AS has_model_performance_results,
    (SELECT count(*) FROM information_schema.tables
       WHERE table_schema = 'core'
         AND table_name = 'llm_exchange_log')            AS has_llm_exchange_log,
    -- Initial partition
    (SELECT count(*) FROM information_schema.tables
       WHERE table_schema = 'core'
         AND table_name = 'llm_exchange_log_2026_05')    AS has_initial_partition,
    -- New columns on existing tables
    (SELECT count(*) FROM information_schema.columns
       WHERE table_schema = 'core'
         AND table_name = 'llm_resources'
         AND column_name IN ('model_name', 'api_url', 'locality',
                             'max_concurrent', 'rate_limit_seconds',
                             'retry_attempts', 'retry_backoff_seconds',
                             'cost_per_token', 'health_status',
                             'last_health_check_at', 'registered_at')) AS llm_resources_new_columns,
    (SELECT count(*) FROM information_schema.columns
       WHERE table_schema = 'core'
         AND table_name = 'cognitive_roles'
         AND column_name = 'operating_mode')             AS cognitive_roles_operating_mode,
    -- FK constraints
    (SELECT count(*) FROM information_schema.table_constraints
       WHERE table_schema = 'core'
         AND table_name = 'semantic_cache'
         AND constraint_name = 'fk_semantic_cache_cognitive_role') AS semantic_cache_fk,
    (SELECT count(*) FROM information_schema.table_constraints
       WHERE table_schema = 'core'
         AND table_name = 'agent_memory'
         AND constraint_name = 'fk_agent_memory_cognitive_role')    AS agent_memory_fk,
    -- Populate completeness
    (SELECT count(*) FROM core.runtime_settings)        AS runtime_settings_rows,
    (SELECT count(*) FROM core.config_migration_log)    AS config_migration_log_rows;

COMMIT;
