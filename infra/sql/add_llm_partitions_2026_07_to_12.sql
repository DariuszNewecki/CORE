-- Migration: add llm_exchange_log monthly partitions for 2026-07 through 2026-12
-- Addresses: missing partition time-bomb (INSERTs fail from 2026-07-01 00:00:00+00)
-- Run against live DB: psql "$DATABASE_URL" -f infra/sql/add_llm_partitions_2026_07_to_12.sql
-- Safe to run once; will error if partitions already exist (idempotency check at top).
--
-- Note: on a live DB, ATTACH PARTITION automatically creates and attaches the PK
-- and all ON ONLY parent indexes. The explicit CREATE INDEX / ALTER INDEX ATTACH
-- statements in pg_dump are for cold restore paths only and must NOT be run here.

BEGIN;

-- Guard: abort if 2026-07 partition already exists to prevent double-apply
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_tables
        WHERE schemaname = 'core' AND tablename = 'llm_exchange_log_2026_07'
    ) THEN
        RAISE EXCEPTION 'Partition llm_exchange_log_2026_07 already exists — migration already applied.';
    END IF;
END $$;

-- ── 2026-07 ──────────────────────────────────────────────────────────────────

CREATE TABLE core.llm_exchange_log_2026_07 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    resource_name text NOT NULL,
    cognitive_role text NOT NULL,
    task_id uuid,
    prompt_tokens integer,
    completion_tokens integer,
    duration_ms integer,
    model_snapshot text NOT NULL,
    cost_estimate numeric(10,6),
    privacy_level text DEFAULT 'standard'::text NOT NULL,
    redacted boolean DEFAULT false NOT NULL,
    ts timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT llm_exchange_log_privacy_check CHECK ((privacy_level = ANY (ARRAY['standard'::text, 'restricted'::text, 'redacted'::text])))
);
ALTER TABLE core.llm_exchange_log_2026_07 OWNER TO core_db;
ALTER TABLE ONLY core.llm_exchange_log
    ATTACH PARTITION core.llm_exchange_log_2026_07
    FOR VALUES FROM ('2026-07-01 00:00:00+00') TO ('2026-08-01 00:00:00+00');

-- ── 2026-08 ──────────────────────────────────────────────────────────────────

CREATE TABLE core.llm_exchange_log_2026_08 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    resource_name text NOT NULL,
    cognitive_role text NOT NULL,
    task_id uuid,
    prompt_tokens integer,
    completion_tokens integer,
    duration_ms integer,
    model_snapshot text NOT NULL,
    cost_estimate numeric(10,6),
    privacy_level text DEFAULT 'standard'::text NOT NULL,
    redacted boolean DEFAULT false NOT NULL,
    ts timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT llm_exchange_log_privacy_check CHECK ((privacy_level = ANY (ARRAY['standard'::text, 'restricted'::text, 'redacted'::text])))
);
ALTER TABLE core.llm_exchange_log_2026_08 OWNER TO core_db;
ALTER TABLE ONLY core.llm_exchange_log
    ATTACH PARTITION core.llm_exchange_log_2026_08
    FOR VALUES FROM ('2026-08-01 00:00:00+00') TO ('2026-09-01 00:00:00+00');

-- ── 2026-09 ──────────────────────────────────────────────────────────────────

CREATE TABLE core.llm_exchange_log_2026_09 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    resource_name text NOT NULL,
    cognitive_role text NOT NULL,
    task_id uuid,
    prompt_tokens integer,
    completion_tokens integer,
    duration_ms integer,
    model_snapshot text NOT NULL,
    cost_estimate numeric(10,6),
    privacy_level text DEFAULT 'standard'::text NOT NULL,
    redacted boolean DEFAULT false NOT NULL,
    ts timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT llm_exchange_log_privacy_check CHECK ((privacy_level = ANY (ARRAY['standard'::text, 'restricted'::text, 'redacted'::text])))
);
ALTER TABLE core.llm_exchange_log_2026_09 OWNER TO core_db;
ALTER TABLE ONLY core.llm_exchange_log
    ATTACH PARTITION core.llm_exchange_log_2026_09
    FOR VALUES FROM ('2026-09-01 00:00:00+00') TO ('2026-10-01 00:00:00+00');

-- ── 2026-10 ──────────────────────────────────────────────────────────────────

CREATE TABLE core.llm_exchange_log_2026_10 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    resource_name text NOT NULL,
    cognitive_role text NOT NULL,
    task_id uuid,
    prompt_tokens integer,
    completion_tokens integer,
    duration_ms integer,
    model_snapshot text NOT NULL,
    cost_estimate numeric(10,6),
    privacy_level text DEFAULT 'standard'::text NOT NULL,
    redacted boolean DEFAULT false NOT NULL,
    ts timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT llm_exchange_log_privacy_check CHECK ((privacy_level = ANY (ARRAY['standard'::text, 'restricted'::text, 'redacted'::text])))
);
ALTER TABLE core.llm_exchange_log_2026_10 OWNER TO core_db;
ALTER TABLE ONLY core.llm_exchange_log
    ATTACH PARTITION core.llm_exchange_log_2026_10
    FOR VALUES FROM ('2026-10-01 00:00:00+00') TO ('2026-11-01 00:00:00+00');

-- ── 2026-11 ──────────────────────────────────────────────────────────────────

CREATE TABLE core.llm_exchange_log_2026_11 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    resource_name text NOT NULL,
    cognitive_role text NOT NULL,
    task_id uuid,
    prompt_tokens integer,
    completion_tokens integer,
    duration_ms integer,
    model_snapshot text NOT NULL,
    cost_estimate numeric(10,6),
    privacy_level text DEFAULT 'standard'::text NOT NULL,
    redacted boolean DEFAULT false NOT NULL,
    ts timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT llm_exchange_log_privacy_check CHECK ((privacy_level = ANY (ARRAY['standard'::text, 'restricted'::text, 'redacted'::text])))
);
ALTER TABLE core.llm_exchange_log_2026_11 OWNER TO core_db;
ALTER TABLE ONLY core.llm_exchange_log
    ATTACH PARTITION core.llm_exchange_log_2026_11
    FOR VALUES FROM ('2026-11-01 00:00:00+00') TO ('2026-12-01 00:00:00+00');

-- ── 2026-12 ──────────────────────────────────────────────────────────────────

CREATE TABLE core.llm_exchange_log_2026_12 (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    resource_name text NOT NULL,
    cognitive_role text NOT NULL,
    task_id uuid,
    prompt_tokens integer,
    completion_tokens integer,
    duration_ms integer,
    model_snapshot text NOT NULL,
    cost_estimate numeric(10,6),
    privacy_level text DEFAULT 'standard'::text NOT NULL,
    redacted boolean DEFAULT false NOT NULL,
    ts timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT llm_exchange_log_privacy_check CHECK ((privacy_level = ANY (ARRAY['standard'::text, 'restricted'::text, 'redacted'::text])))
);
ALTER TABLE core.llm_exchange_log_2026_12 OWNER TO core_db;
ALTER TABLE ONLY core.llm_exchange_log
    ATTACH PARTITION core.llm_exchange_log_2026_12
    FOR VALUES FROM ('2026-12-01 00:00:00+00') TO ('2027-01-01 00:00:00+00');

COMMIT;
