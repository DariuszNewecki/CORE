-- Create llm_exchange_log monthly partitions for 2026-07 through 2026-12.
-- Date: 2026-06-26
--
-- External review finding: the 2026-07 partition was missing; INSERT would
-- fail from July 1 with no matching partition. This migration adds all six
-- remaining 2026 partitions and attaches their local indexes to the parent
-- partitioned indexes (role_ts_idx, resource_ts_idx, task_idx, pkey).

BEGIN;

-- ── 2026-07 ────────────────────────────────────────────────────────────────

CREATE TABLE core.llm_exchange_log_2026_07
    PARTITION OF core.llm_exchange_log
    FOR VALUES FROM ('2026-07-01 00:00:00+00') TO ('2026-08-01 00:00:00+00');

ALTER TABLE ONLY core.llm_exchange_log_2026_07
    ADD CONSTRAINT llm_exchange_log_2026_07_pkey PRIMARY KEY (id, ts);

CREATE INDEX llm_exchange_log_2026_07_cognitive_role_ts_idx
    ON core.llm_exchange_log_2026_07 USING btree (cognitive_role, ts DESC);
CREATE INDEX llm_exchange_log_2026_07_resource_name_ts_idx
    ON core.llm_exchange_log_2026_07 USING btree (resource_name, ts DESC);
CREATE INDEX llm_exchange_log_2026_07_task_id_idx
    ON core.llm_exchange_log_2026_07 USING btree (task_id);

ALTER INDEX core.llm_exchange_log_pkey
    ATTACH PARTITION core.llm_exchange_log_2026_07_pkey;
ALTER INDEX core.llm_exchange_log_role_ts_idx
    ATTACH PARTITION core.llm_exchange_log_2026_07_cognitive_role_ts_idx;
ALTER INDEX core.llm_exchange_log_resource_ts_idx
    ATTACH PARTITION core.llm_exchange_log_2026_07_resource_name_ts_idx;
ALTER INDEX core.llm_exchange_log_task_idx
    ATTACH PARTITION core.llm_exchange_log_2026_07_task_id_idx;

-- ── 2026-08 ────────────────────────────────────────────────────────────────

CREATE TABLE core.llm_exchange_log_2026_08
    PARTITION OF core.llm_exchange_log
    FOR VALUES FROM ('2026-08-01 00:00:00+00') TO ('2026-09-01 00:00:00+00');

ALTER TABLE ONLY core.llm_exchange_log_2026_08
    ADD CONSTRAINT llm_exchange_log_2026_08_pkey PRIMARY KEY (id, ts);

CREATE INDEX llm_exchange_log_2026_08_cognitive_role_ts_idx
    ON core.llm_exchange_log_2026_08 USING btree (cognitive_role, ts DESC);
CREATE INDEX llm_exchange_log_2026_08_resource_name_ts_idx
    ON core.llm_exchange_log_2026_08 USING btree (resource_name, ts DESC);
CREATE INDEX llm_exchange_log_2026_08_task_id_idx
    ON core.llm_exchange_log_2026_08 USING btree (task_id);

ALTER INDEX core.llm_exchange_log_pkey
    ATTACH PARTITION core.llm_exchange_log_2026_08_pkey;
ALTER INDEX core.llm_exchange_log_role_ts_idx
    ATTACH PARTITION core.llm_exchange_log_2026_08_cognitive_role_ts_idx;
ALTER INDEX core.llm_exchange_log_resource_ts_idx
    ATTACH PARTITION core.llm_exchange_log_2026_08_resource_name_ts_idx;
ALTER INDEX core.llm_exchange_log_task_idx
    ATTACH PARTITION core.llm_exchange_log_2026_08_task_id_idx;

-- ── 2026-09 ────────────────────────────────────────────────────────────────

CREATE TABLE core.llm_exchange_log_2026_09
    PARTITION OF core.llm_exchange_log
    FOR VALUES FROM ('2026-09-01 00:00:00+00') TO ('2026-10-01 00:00:00+00');

ALTER TABLE ONLY core.llm_exchange_log_2026_09
    ADD CONSTRAINT llm_exchange_log_2026_09_pkey PRIMARY KEY (id, ts);

CREATE INDEX llm_exchange_log_2026_09_cognitive_role_ts_idx
    ON core.llm_exchange_log_2026_09 USING btree (cognitive_role, ts DESC);
CREATE INDEX llm_exchange_log_2026_09_resource_name_ts_idx
    ON core.llm_exchange_log_2026_09 USING btree (resource_name, ts DESC);
CREATE INDEX llm_exchange_log_2026_09_task_id_idx
    ON core.llm_exchange_log_2026_09 USING btree (task_id);

ALTER INDEX core.llm_exchange_log_pkey
    ATTACH PARTITION core.llm_exchange_log_2026_09_pkey;
ALTER INDEX core.llm_exchange_log_role_ts_idx
    ATTACH PARTITION core.llm_exchange_log_2026_09_cognitive_role_ts_idx;
ALTER INDEX core.llm_exchange_log_resource_ts_idx
    ATTACH PARTITION core.llm_exchange_log_2026_09_resource_name_ts_idx;
ALTER INDEX core.llm_exchange_log_task_idx
    ATTACH PARTITION core.llm_exchange_log_2026_09_task_id_idx;

-- ── 2026-10 ────────────────────────────────────────────────────────────────

CREATE TABLE core.llm_exchange_log_2026_10
    PARTITION OF core.llm_exchange_log
    FOR VALUES FROM ('2026-10-01 00:00:00+00') TO ('2026-11-01 00:00:00+00');

ALTER TABLE ONLY core.llm_exchange_log_2026_10
    ADD CONSTRAINT llm_exchange_log_2026_10_pkey PRIMARY KEY (id, ts);

CREATE INDEX llm_exchange_log_2026_10_cognitive_role_ts_idx
    ON core.llm_exchange_log_2026_10 USING btree (cognitive_role, ts DESC);
CREATE INDEX llm_exchange_log_2026_10_resource_name_ts_idx
    ON core.llm_exchange_log_2026_10 USING btree (resource_name, ts DESC);
CREATE INDEX llm_exchange_log_2026_10_task_id_idx
    ON core.llm_exchange_log_2026_10 USING btree (task_id);

ALTER INDEX core.llm_exchange_log_pkey
    ATTACH PARTITION core.llm_exchange_log_2026_10_pkey;
ALTER INDEX core.llm_exchange_log_role_ts_idx
    ATTACH PARTITION core.llm_exchange_log_2026_10_cognitive_role_ts_idx;
ALTER INDEX core.llm_exchange_log_resource_ts_idx
    ATTACH PARTITION core.llm_exchange_log_2026_10_resource_name_ts_idx;
ALTER INDEX core.llm_exchange_log_task_idx
    ATTACH PARTITION core.llm_exchange_log_2026_10_task_id_idx;

-- ── 2026-11 ────────────────────────────────────────────────────────────────

CREATE TABLE core.llm_exchange_log_2026_11
    PARTITION OF core.llm_exchange_log
    FOR VALUES FROM ('2026-11-01 00:00:00+00') TO ('2026-12-01 00:00:00+00');

ALTER TABLE ONLY core.llm_exchange_log_2026_11
    ADD CONSTRAINT llm_exchange_log_2026_11_pkey PRIMARY KEY (id, ts);

CREATE INDEX llm_exchange_log_2026_11_cognitive_role_ts_idx
    ON core.llm_exchange_log_2026_11 USING btree (cognitive_role, ts DESC);
CREATE INDEX llm_exchange_log_2026_11_resource_name_ts_idx
    ON core.llm_exchange_log_2026_11 USING btree (resource_name, ts DESC);
CREATE INDEX llm_exchange_log_2026_11_task_id_idx
    ON core.llm_exchange_log_2026_11 USING btree (task_id);

ALTER INDEX core.llm_exchange_log_pkey
    ATTACH PARTITION core.llm_exchange_log_2026_11_pkey;
ALTER INDEX core.llm_exchange_log_role_ts_idx
    ATTACH PARTITION core.llm_exchange_log_2026_11_cognitive_role_ts_idx;
ALTER INDEX core.llm_exchange_log_resource_ts_idx
    ATTACH PARTITION core.llm_exchange_log_2026_11_resource_name_ts_idx;
ALTER INDEX core.llm_exchange_log_task_idx
    ATTACH PARTITION core.llm_exchange_log_2026_11_task_id_idx;

-- ── 2026-12 ────────────────────────────────────────────────────────────────

CREATE TABLE core.llm_exchange_log_2026_12
    PARTITION OF core.llm_exchange_log
    FOR VALUES FROM ('2026-12-01 00:00:00+00') TO ('2027-01-01 00:00:00+00');

ALTER TABLE ONLY core.llm_exchange_log_2026_12
    ADD CONSTRAINT llm_exchange_log_2026_12_pkey PRIMARY KEY (id, ts);

CREATE INDEX llm_exchange_log_2026_12_cognitive_role_ts_idx
    ON core.llm_exchange_log_2026_12 USING btree (cognitive_role, ts DESC);
CREATE INDEX llm_exchange_log_2026_12_resource_name_ts_idx
    ON core.llm_exchange_log_2026_12 USING btree (resource_name, ts DESC);
CREATE INDEX llm_exchange_log_2026_12_task_id_idx
    ON core.llm_exchange_log_2026_12 USING btree (task_id);

ALTER INDEX core.llm_exchange_log_pkey
    ATTACH PARTITION core.llm_exchange_log_2026_12_pkey;
ALTER INDEX core.llm_exchange_log_role_ts_idx
    ATTACH PARTITION core.llm_exchange_log_2026_12_cognitive_role_ts_idx;
ALTER INDEX core.llm_exchange_log_resource_ts_idx
    ATTACH PARTITION core.llm_exchange_log_2026_12_resource_name_ts_idx;
ALTER INDEX core.llm_exchange_log_task_idx
    ATTACH PARTITION core.llm_exchange_log_2026_12_task_id_idx;

COMMIT;
