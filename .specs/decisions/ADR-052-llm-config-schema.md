# ADR-052 — LLM Configuration Domain: Final Schema

**Status:** Accepted
**Date:** 2026-05-16
**Domain:** Infrastructure / LLM Configuration
**Band:** D — Engine Integrity
**Replaces:** implicit schema carried by `runtime_settings` since initial .env migration
**Closes:** #268 (partial), surfaces schema work for G4 cleanup

---

## Context

During initial CORE setup, all non-DB configuration lived in `.env`. A decision was made
that `.env` must carry only DB connection settings — everything else must live in the
database. At that time, not all destination tables existed, so `runtime_settings` was
introduced as a transitional key-value store: a DB-based copy of `.env` with the same
flat, untyped, key=value structure.

Proper tables (`llm_resources`, `cognitive_roles`) were subsequently created, but the
migration from `runtime_settings` into those tables was never completed. The result is a
split configuration state:

- `llm_resources` holds 16 registry entries but is missing typed columns for `model_name`,
  `api_url`, and concurrency settings — those still live as strings in `runtime_settings`.
- `runtime_settings` references 11 resource-shaped key prefixes, of which only 7 match
  entries in `llm_resources`. The remaining 4 in each direction are orphans.
- Three keys (`LLM_ENABLED`, `llm.enabled`, `system.llm_enabled`) encode the same boolean
  with different `last_updated` timestamps — silent divergence risk.
- Two rate-limit naming conventions coexist (`_max_concurrent.requests` vs `.max_concurrent`)
  with no enforcement.
- Four external providers are marked `is_available=true` in `llm_resources` despite a
  local-only routing policy — the DB contradicts the policy.
- `cognitive_roles.assigned_resource` is a single FK — no primary/secondary fallback is
  expressible.
- `semantic_cache.cognitive_role` and `agent_memory.cognitive_role` are untyped text with
  no FK enforcement.

A comparison against LiteLLM, LangSmith, MLflow, and Portkey identified additional gaps:
cost tracking, automatic health checking, retry configuration per resource, PII handling
on exchange logs, and a structured capability alignment benchmark system.

This ADR defines the complete target schema for the LLM configuration domain, the
migration path from `runtime_settings`, and the retirement criteria for that table.

---

## Decision

### Governing principles

1. `llm_resources` is the single source of truth for every resource-specific property.
   No resource property may live in `runtime_settings` or any other table.
2. `runtime_settings` is retired once every row in `config_migration_log` carries a
   non-null `migrated_at`. Until then it remains readable but no new rows are written.
3. Credentials (API keys) move to `secret_store` — a typed, auditable replacement for
   the `is_secret=true` subset of `runtime_settings`.
4. System-wide operational flags move to `system_config` — a typed singleton table.
   One canonical row. One canonical key per concept.
5. `cognitive_roles.assigned_resource` is replaced by the `role_resource_assignments`
   join table, supporting priority-ordered resource lists per role.
6. Operating mode (`local_only` / `remote_only` / `hybrid`) is declared at system level
   in `system_config` and may be overridden per role in `cognitive_roles`. The system
   default wins when no role override is set.
7. Every new `llm_resources` registration triggers a capability alignment benchmark run.
   Results are persisted in `model_performance_results`.
8. Every CORE-LLM exchange is appended to `llm_exchange_log` (append-only, no updates,
   no deletes). `model_snapshot` captures the model name at call time.

---

## Target Schema

### New tables

#### `role_resource_assignments`
Replaces `cognitive_roles.assigned_resource` (single FK → unenforceable fallback).

```sql
CREATE TABLE core.role_resource_assignments (
    role        text        NOT NULL REFERENCES core.cognitive_roles(role)
                            ON UPDATE CASCADE ON DELETE CASCADE,
    resource    text        NOT NULL REFERENCES core.llm_resources(name)
                            ON UPDATE CASCADE ON DELETE RESTRICT,
    priority    integer     NOT NULL CHECK (priority >= 1),
    is_active   boolean     NOT NULL DEFAULT true,
    assigned_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (role, resource)
);
CREATE UNIQUE INDEX ON core.role_resource_assignments (role, priority) WHERE is_active;
```

`priority = 1` is primary. `priority = 2` is secondary fallback. The partial unique index
prevents two active assignments at the same priority for the same role.

---

#### `system_config`
Single-row typed table. Replaces the three duplicate `llm_enabled` flags and all
system-wide operational settings currently in `runtime_settings`.

```sql
CREATE TABLE core.system_config (
    id                      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    operating_mode          text        NOT NULL DEFAULT 'local_only'
                            CHECK (operating_mode IN ('local_only','remote_only','hybrid')),
    llm_enabled             boolean     NOT NULL DEFAULT true,
    request_timeout_seconds integer     NOT NULL DEFAULT 300,
    embed_model_revision    text,
    updated_at              timestamptz NOT NULL DEFAULT now()
);
```

One row enforced at application level. `operating_mode` here is the system-wide default;
per-role overrides live in `cognitive_roles.operating_mode`.

---

#### `secret_store`
Typed replacement for `runtime_settings` rows where `is_secret = true`.

```sql
CREATE TABLE core.secret_store (
    key             text        PRIMARY KEY,
    resource_name   text        REFERENCES core.llm_resources(name)
                                ON UPDATE CASCADE ON DELETE SET NULL,
    value           text        NOT NULL,
    last_rotated_at timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);
```

Key convention: `{env_prefix}.api_key` — identical to existing `runtime_settings`
convention so `ConfigService` requires minimal change. `resource_name` FK enables
"list all credentials for a resource" without parsing the key string.

---

#### `config_migration_log`
Audit trail for the `.env` → `runtime_settings` → proper table journey.
Two timestamps per record provide full traceability.

```sql
CREATE TABLE core.config_migration_log (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    env_key             text        NOT NULL,
    source              text        NOT NULL CHECK (source IN ('dotenv','runtime_settings')),
    destination_table   text        NOT NULL,
    destination_column  text        NOT NULL,
    imported_at         timestamptz NOT NULL,
    migrated_at         timestamptz,
    migrated_by         text        NOT NULL
);
```

`imported_at` = when the value landed in `runtime_settings`.
`migrated_at` = when it moved to its proper table. NULL means still in transit.
When all rows carry `migrated_at`, `runtime_settings` may be dropped.

---

#### `capability_alignment_tests`
Defines the benchmark test suite run against every registered model.

```sql
CREATE TABLE core.capability_alignment_tests (
    id               uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
    name             text    NOT NULL UNIQUE,
    capability       text    NOT NULL,
    expected_behavior text   NOT NULL,
    scoring_rubric   jsonb   NOT NULL DEFAULT '{}',
    created_at       timestamptz NOT NULL DEFAULT now()
);
```

`capability` references the canonical capability taxonomy in `.intent/`. The constitutional
rule `capability.taxonomy.no_ad_hoc_capabilities` applies to this column.

---

#### `model_performance_results`
Benchmark results per model per test. Triggered on registration; repeatable manually
or on schedule.

```sql
CREATE TABLE core.model_performance_results (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_name   text        NOT NULL REFERENCES core.llm_resources(name)
                                ON UPDATE CASCADE ON DELETE CASCADE,
    test_id         uuid        NOT NULL REFERENCES core.capability_alignment_tests(id)
                                ON DELETE RESTRICT,
    score           numeric(5,2) NOT NULL CHECK (score BETWEEN 0 AND 100),
    notes           text,
    triggered_by    text        NOT NULL
                    CHECK (triggered_by IN ('registration','manual','scheduled')),
    evaluated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON core.model_performance_results (resource_name, evaluated_at DESC);

-- Deduplication guard: a model may only have one registration benchmark per test.
-- Prevents duplicate rows on daemon restart mid-registration.
-- To re-run a registration benchmark, delete the existing row explicitly (governor action).
-- Manual and scheduled runs are unrestricted.
CREATE UNIQUE INDEX ON core.model_performance_results (resource_name, test_id)
    WHERE triggered_by = 'registration';
```

---

#### `llm_exchange_log`
Append-only record of every CORE-LLM interaction. No UPDATE, no DELETE.

Partitioned by month on `ts` to support long-term retention without unbounded table
growth. For GxP deployments (EU Annex 11), partitions are never dropped — old partitions
are moved to a `core_archive` schema. For non-GxP deployments, a shorter retention
window may be configured, but the partition structure is identical.

```sql
CREATE TABLE core.llm_exchange_log (
    id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_name     text        NOT NULL REFERENCES core.llm_resources(name)
                                  ON UPDATE CASCADE ON DELETE RESTRICT,
    cognitive_role    text        NOT NULL REFERENCES core.cognitive_roles(role)
                                  ON UPDATE CASCADE ON DELETE RESTRICT,
    task_id           uuid        REFERENCES core.tasks(id) ON DELETE SET NULL,
    prompt_tokens     integer,
    completion_tokens integer,
    duration_ms       integer,
    model_snapshot    text        NOT NULL,
    cost_estimate     numeric(10,6),
    privacy_level     text        NOT NULL DEFAULT 'standard'
                      CHECK (privacy_level IN ('standard','restricted','redacted')),
    redacted          boolean     NOT NULL DEFAULT false,
    ts                timestamptz NOT NULL DEFAULT now()
) PARTITION BY RANGE (ts);

-- Initial partition — one per month, created by maintenance job before month begins.
CREATE TABLE core.llm_exchange_log_2026_05
    PARTITION OF core.llm_exchange_log
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

CREATE INDEX ON core.llm_exchange_log (resource_name, ts DESC);
CREATE INDEX ON core.llm_exchange_log (cognitive_role, ts DESC);
CREATE INDEX ON core.llm_exchange_log (task_id);
```

`model_snapshot` captures `model_name` at call time — survives resource reconfiguration.
`privacy_level = 'redacted'` + `redacted = true` signals PII scrubbing has been applied.

**Retention policy (GxP):** partitions older than the active window are moved to
`core_archive` schema, never dropped. Retention duration = product lifetime + 1 year
(EU GxP Annex 11 minimum).

**Retention policy (standard):** configurable in `system_config`; default 24 months.

---

### Modified tables

#### `llm_resources` — new typed columns

```sql
ALTER TABLE core.llm_resources
    ADD COLUMN model_name           text,
    ADD COLUMN api_url              text,
    ADD COLUMN locality             text NOT NULL DEFAULT 'local'
                                    CHECK (locality IN ('local','remote')),
    ADD COLUMN max_concurrent       integer NOT NULL DEFAULT 1,
    ADD COLUMN rate_limit_seconds   integer NOT NULL DEFAULT 0,
    ADD COLUMN retry_attempts       integer NOT NULL DEFAULT 0,
    ADD COLUMN retry_backoff_seconds integer NOT NULL DEFAULT 5,
    ADD COLUMN cost_per_token       numeric(12,8),
    ADD COLUMN health_status        text DEFAULT 'unknown'
                                    CHECK (health_status IN ('healthy','degraded','unavailable','unknown')),
    ADD COLUMN last_health_check_at timestamptz,
    ADD COLUMN registered_at        timestamptz NOT NULL DEFAULT now();
```

After data migration from `runtime_settings`, add NOT NULL constraints to `model_name`.
`env_prefix` is retained solely as the credential key prefix for `secret_store` lookup.
`performance_metadata` jsonb is retained for freeform notes but is no longer the
authoritative source for cost, concurrency, or health data.

---

#### `cognitive_roles` — add operating_mode, remove assigned_resource

```sql
ALTER TABLE core.cognitive_roles
    ADD COLUMN operating_mode text
                CHECK (operating_mode IN ('local_only','remote_only','hybrid'));

ALTER TABLE core.cognitive_roles
    DROP COLUMN assigned_resource;
```

`operating_mode NULL` means: inherit from `system_config.operating_mode`.
`assigned_resource` is replaced by `role_resource_assignments`.

---

#### `semantic_cache` — add FK

```sql
ALTER TABLE core.semantic_cache
    ADD CONSTRAINT fk_semantic_cache_cognitive_role
    FOREIGN KEY (cognitive_role) REFERENCES core.cognitive_roles(role)
    ON UPDATE CASCADE ON DELETE RESTRICT;
```

`llm_model` (raw model string) retains no FK — cache entries must survive resource
renames and remain queryable by underlying model string.

---

#### `agent_memory` — add FK

```sql
ALTER TABLE core.agent_memory
    ADD CONSTRAINT fk_agent_memory_cognitive_role
    FOREIGN KEY (cognitive_role) REFERENCES core.cognitive_roles(role)
    ON UPDATE CASCADE ON DELETE RESTRICT;
```

---

### Retired tables

#### `runtime_settings`
Retired once `config_migration_log` shows zero rows with `migrated_at IS NULL`.

Migration completion query:
```sql
SELECT COUNT(*) FROM core.config_migration_log WHERE migrated_at IS NULL;
-- Must return 0 before DROP TABLE is permitted.
```

Drop sequence:
```sql
DROP TABLE core.runtime_settings;
```

---

## Migration path

### Phase 1 — Additive (no breakage)
1. Create all new tables.
2. Add new columns to `llm_resources` and `cognitive_roles` as nullable.
3. Add FKs to `semantic_cache` and `agent_memory`.
4. Populate `config_migration_log` with all current `runtime_settings` rows
   (`imported_at` from `runtime_settings.last_updated`, `migrated_at = NULL`).

### Phase 2 — Data migration
5. For each resource in `llm_resources`, read `{env_prefix}.api_url`,
   `{env_prefix}.model_name`, and concurrency settings from `runtime_settings`,
   write to typed columns, update `config_migration_log.migrated_at`.
6. Migrate `{env_prefix}.api_key` rows to `secret_store`.
7. Collapse three `llm_enabled` flags into one `system_config` row.
8. Migrate system-wide settings (`request_timeout`, `embed_model_revision`) to
   `system_config`.
9. Populate `role_resource_assignments` from current `cognitive_roles.assigned_resource`
   values (all as `priority = 1`).

### Phase 3 — Enforcement
10. Add NOT NULL constraint to `llm_resources.model_name`.
11. Drop `cognitive_roles.assigned_resource`.
12. Add `is_migration_complete() -> bool` to `ConfigService`:
    ```python
    async def is_migration_complete(self) -> bool:
        result = await self._session.execute(
            text("SELECT COUNT(*) FROM core.config_migration_log WHERE migrated_at IS NULL")
        )
        return result.scalar() == 0
    ```
    `ConfigService` reads from typed columns and `secret_store` when this returns `True`;
    falls back to `runtime_settings` when `False`. Cutover is data-driven — no feature
    flag, no manual switch, no deployment coordination required. The daemon detects
    readiness automatically on next startup.
13. Verify `config_migration_log` — zero `migrated_at IS NULL`.

### Phase 4 — Retirement
14. Drop `runtime_settings`.

---

## Consequences

**Positive:**
- Single source of truth for all resource configuration.
- Naming convention fragmentation eliminated — typed columns enforce one schema.
- Primary/secondary fallback expressible without schema changes.
- Operating mode policy enforced at DB level, not only in application code.
- Full causal traceability for configuration values from `.env` to final table.
- Exchange log enables cost tracking, performance analysis, and GxP audit evidence.
- Capability alignment benchmark system provides ranked, comparable model registry.
- Health status and retry configuration close gaps vs LiteLLM/Portkey.
- `runtime_settings` retirement removes the largest source of configuration drift.

**Negative / risks:**
- Phase 2/3 cutover is data-driven via `ConfigService.is_migration_complete()` —
  no manual switch required, but Phase 2 must complete fully before the daemon
  restart that activates Phase 3 reads. Partial migration leaves some resources
  unreadable.
- `cognitive_roles.assigned_resource` DROP in Phase 3 requires `role_resource_assignments`
  to be fully populated first. Verify row count matches before dropping.
- `llm_exchange_log` is partitioned by month. A maintenance job must create the next
  month's partition before the month begins — failure leaves the log unwritable for
  that period. Add partition creation to the CORE maintenance schedule.

---

## References

- ADR-008 — impact_level governance
- ADR-018 — VectorSyncWorker retirement
- ADR-031 — no hardcoded runtime directory paths
- `core.runtime_settings` discovery: 2026-05-16 session
- `core.llm_resources` / `core.cognitive_roles` discovery: 2026-05-16 session
- CORE-A3-plan.md — Band D, Milestone 16
