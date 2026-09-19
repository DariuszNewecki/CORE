-- Retire core.llm_resources.cost_per_token (follow-on to #620).
-- Date: 2026-06-13
--
-- The column (added by 20260516_adr_052_phase1_llm_config_schema.sql) was
-- NULL on all 16 resource rows for its entire lifetime and read by no
-- business logic — only a mapped_column definition in
-- shared.infrastructure.database.models.operations. A single blended
-- per-token rate also cannot express the input/output split that real
-- pricing needs. #620 introduced core.llm_resource_rates (model-keyed,
-- input/output split, append-only) which supersedes it.
--
-- No live view or function depends on llm_resources (verified via
-- pg_depend). Dropping an all-NULL column loses no data.
--
-- Apply AFTER 20260613_llm_resource_rates.sql.

BEGIN;

ALTER TABLE core.llm_resources DROP COLUMN cost_per_token;

COMMIT;
