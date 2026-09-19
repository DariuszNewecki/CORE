-- 20260516_adr_052_phase3_enforcement_cutover.sql
--
-- Phase 3 of ADR-052 — enforcement cutover.
-- Locks in the post-Phase-2 schema by adding the integrity constraint
-- on llm_resources.model_name and dropping the deprecated
-- cognitive_roles.assigned_resource column.
--
-- Phase 4 (drop runtime_settings) is gated on
-- ConfigService.is_migration_complete() returning True, which itself
-- gates on every config_migration_log row carrying a non-null
-- migrated_at. Today 20 cml rows remain pending (see #331 for the
-- 8 orphan resource keys; the other 12 are non-LLM operational
-- settings out of ADR-052 scope). Phase 3 lands regardless, because
-- nothing in Phase 3 itself requires migration completeness — the
-- ConfigService dual-path read continues to fall back to
-- runtime_settings while pending rows remain.
--
-- DEVIATION FROM ADR-052
--
-- ADR-052 Phase 3 specifies:
--
--   ALTER TABLE core.llm_resources ALTER COLUMN model_name SET NOT NULL;
--
-- This cannot be applied today: five rows have model_name IS NULL,
-- all of them marked is_available=false by governor decision C
-- (commit 8085c322). Bare SET NOT NULL would error on those rows.
-- Two options were considered:
--
--   * Backfill the five rows with a sentinel model_name. Rejected —
--     a sentinel violates ADR-052's governing principle #1
--     ("llm_resources is the single source of truth for every
--     resource-specific property"); a fake model_name is worse than
--     no model_name.
--   * Replace the unconditional NOT NULL with a partial CHECK:
--     `is_available = false OR model_name IS NOT NULL`. This enforces
--     the ADR's actual intent — every active resource has a real
--     model_name — while accommodating the governor's choice to
--     keep five unconfigured rows in the registry.
--
-- This migration takes the partial-CHECK path. ADR-052 will be
-- amended in the same commit to record the deviation, matching the
-- pattern set by the Phase 1 PK deviation (commit a6c5fd35,
-- amendment commit bc29506c).
--
-- IDEMPOTENCY
--
-- Forward-only. Re-running is a safe no-op:
--   * CHECK constraint creation guarded by a constraint-name lookup.
--   * DROP COLUMN uses IF EXISTS.
--
-- VERIFICATION
--
-- The trailing SELECT reports:
--   * Whether the model_name CHECK constraint is in place.
--   * Whether cognitive_roles.assigned_resource still exists (0 if dropped).
--   * Active resources vs. resources with model_name (must agree).
--
-- References:
--   * ADR-052 — LLM Configuration Domain: Final Schema
--   * Issue #327 — Phase 3 tracking issue
--   * Phase 1: commit a6c5fd35
--   * Phase 2: commit 8398483e
--   * Governor decisions A–E: commit 8085c322

BEGIN;

-- =========================================================================
-- 1. llm_resources — partial CHECK on model_name (see deviation note above).
-- =========================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_schema = 'core'
          AND table_name = 'llm_resources'
          AND constraint_name = 'llm_resources_available_requires_model_name'
    ) THEN
        ALTER TABLE core.llm_resources
            ADD CONSTRAINT llm_resources_available_requires_model_name
            CHECK (is_available = false OR model_name IS NOT NULL);
    END IF;
END
$$;

-- =========================================================================
-- 2. cognitive_roles — drop the deprecated assigned_resource column.
-- =========================================================================
-- Replaced by core.role_resource_assignments (priority-ordered FK list).
-- Phase 2 (commit 8398483e) populated 10 priority=1 rows, one per
-- pre-existing assigned_resource value. Verified before this migration:
-- roles_with_assigned = 10, rra_priority_1 = 10.
--
-- The view `core.v_agent_workload` (operator dashboard) references the
-- column. Drop and recreate it against `role_resource_assignments`
-- (priority=1 active assignment) so the surface stays stable.

DROP VIEW IF EXISTS core.v_agent_workload;

ALTER TABLE core.cognitive_roles
    DROP COLUMN IF EXISTS assigned_resource;

CREATE OR REPLACE VIEW core.v_agent_workload AS
SELECT
    cr.role,
    cr.is_active,
    count(t.id) FILTER (WHERE t.status = 'executing'::text)  AS active_tasks,
    count(t.id) FILTER (WHERE t.status = 'pending'::text)    AS queued_tasks,
    count(t.id) FILTER (WHERE t.status = 'blocked'::text)    AS blocked_tasks,
    cr.max_concurrent_tasks,
    cr.max_concurrent_tasks
        - count(t.id) FILTER (WHERE t.status = 'executing'::text) AS available_slots,
    (
        SELECT rra.resource
        FROM core.role_resource_assignments rra
        WHERE rra.role = cr.role AND rra.is_active = true
        ORDER BY rra.priority
        LIMIT 1
    ) AS assigned_resource
FROM core.cognitive_roles cr
LEFT JOIN core.tasks t
       ON t.assigned_role = cr.role
      AND t.status = ANY (ARRAY['pending','executing','blocked']::text[])
GROUP BY cr.role, cr.is_active, cr.max_concurrent_tasks
ORDER BY cr.role;

-- =========================================================================
-- Verification
-- =========================================================================

SELECT
    (SELECT count(*) FROM information_schema.table_constraints
        WHERE table_schema = 'core'
          AND table_name = 'llm_resources'
          AND constraint_name = 'llm_resources_available_requires_model_name')
        AS has_model_name_check,
    (SELECT count(*) FROM information_schema.columns
        WHERE table_schema = 'core'
          AND table_name = 'cognitive_roles'
          AND column_name = 'assigned_resource')
        AS assigned_resource_remains,
    (SELECT count(*) FROM information_schema.views
        WHERE table_schema = 'core'
          AND table_name = 'v_agent_workload')
        AS has_workload_view,
    (SELECT count(*) FROM core.llm_resources WHERE is_available = true)
        AS active_resources,
    (SELECT count(*) FROM core.llm_resources
        WHERE is_available = true AND model_name IS NOT NULL)
        AS active_with_model_name,
    (SELECT count(*) FROM core.role_resource_assignments
        WHERE priority = 1 AND is_active = true)
        AS active_priority_1_assignments;

COMMIT;
