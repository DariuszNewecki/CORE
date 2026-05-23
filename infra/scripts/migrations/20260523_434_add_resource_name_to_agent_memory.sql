-- #434: agent_memory FK violation — add resource_name column for resource-context audits.
-- Date: 2026-05-23
--
-- secrets_service._audit_secret_access wrote llm_resources.name values
-- (e.g. 'deepseek_chat') into agent_memory.cognitive_role, which has a FK
-- to cognitive_roles.role (values: 'Architect', 'Coder', 'Planner', …).
-- The two value spaces are disjoint, so every remote-LLM secret access
-- fired ForeignKeyViolationError and the audit trail was silently empty.
--
-- This migration adds a sibling column for resource-context audit events.
-- cognitive_role becomes nullable so a row can carry either column.
-- At least one of (cognitive_role, resource_name) is expected to be set,
-- but no CHECK constraint is added — secrets_service enforces this in code
-- by defaulting to resource_name='system' when neither is provided.

BEGIN;

ALTER TABLE core.agent_memory
    ADD COLUMN resource_name TEXT NULL;

ALTER TABLE core.agent_memory
    ALTER COLUMN cognitive_role DROP NOT NULL;

COMMENT ON COLUMN core.agent_memory.resource_name IS
    'Free-text identifier of the access source for resource-context audit '
    'events (e.g. llm_resources.name like ''deepseek_chat''). Distinct from '
    'cognitive_role which carries cognitive_roles.role values via FK. '
    'Exactly one of (cognitive_role, resource_name) should be non-NULL per row.';

COMMIT;
