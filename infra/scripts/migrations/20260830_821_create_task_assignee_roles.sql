-- 20260830_821_create_task_assignee_roles.sql
--
-- #821 Unit 1: separates task-assignee/actor roles from LLM cognitive-role
-- storage. core.cognitive_roles is the projection target of the
-- constitutional cognitive-role taxonomy (.intent/taxonomies/cognitive_roles.yaml,
-- ADR-090 D1) and must contain ONLY LLM-routed cognitive roles. Three of its
-- 14 rows (AutonomousDeveloper, Human, StrategicAuditor) are task-assignee/
-- actor values with no cognitive capabilities and no YAML counterpart --
-- confirmed live, referenced code (core.tasks.assigned_role consumers in
-- development_routes.py, campaign_review.py, strategic_auditor/effects.py),
-- not dead rows. Verified 2026-08-30 against the live DB: none of the five
-- genuine LLM-invocation FK columns (actions/agent_memory/semantic_cache/
-- llm_exchange_log.cognitive_role, role_resource_assignments.role) hold any
-- of the 3 actor values; core.tasks.assigned_role currently holds ONLY
-- actor values (44 rows: 28 AutonomousDeveloper, 12 Human, 4 StrategicAuditor).
--
-- core.task_assignee_roles becomes the operational registry of every value
-- legitimately assignable to core.tasks.assigned_role, discriminated by
-- `kind` (actor | cognitive). Cognitive roles may also be assignable --
-- their capabilities remain governed exclusively by core.cognitive_roles /
-- the YAML taxonomy; no capability column is duplicated here.
--
-- Sequencing (single transaction -- this is a single-developer install with
-- one DB, so full atomicity substitutes for a staged dual-write rollout):
--   1. Create the registry table.
--   2. Seed all 14 currently-legal role values (the exact pre-migration
--      cognitive_roles_role_check vocabulary), so every historical
--      core.tasks.assigned_role reference -- actor or cognitive -- resolves
--      against the new table without exception.
--   3. Add the new FK from core.tasks.assigned_role to the new table.
--   4. Drop the old FK to core.cognitive_roles (must precede step 5 -- its
--      ON DELETE RESTRICT would otherwise block deleting the 3 actor rows
--      for any historical task still holding those values).
--   5. Delete the 3 actor rows from core.cognitive_roles and shrink its
--      CHECK constraint to the 11 real LLM-routed roles.
--   6. Repoint core.v_agent_workload to drive from the new registry (so
--      actor-role task workload is also visible), left-joining
--      cognitive_roles for the cognitive-only is_active/resource columns.
--      core.v_agent_context needs no change -- verified: it never joins
--      cognitive_roles directly, only compares agent_memory.cognitive_role
--      to tasks.assigned_role by value, which is unaffected by which table
--      assigned_role's FK targets.
--   7. Self-verify: no cognitive_roles row remains for the 3 actor names,
--      and every distinct historical core.tasks.assigned_role value
--      resolves in task_assignee_roles.
--
-- The migration ledger (core._migrations) is what prevents re-application,
-- not idempotent SQL within this file -- matching every other migration in
-- this manifest.

BEGIN;

-- 1. Registry table.
CREATE TABLE core.task_assignee_roles (
    role text PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN ('actor', 'cognitive')),
    description text,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE core.task_assignee_roles IS
    'Operational registry of every value legitimately assignable to core.tasks.assigned_role (#821). '
    'kind=actor rows (AutonomousDeveloper, Human, StrategicAuditor) are task-assignee values with no '
    'LLM capability; kind=cognitive rows mirror core.cognitive_roles by name only -- capabilities '
    'remain governed exclusively there, never duplicated here.';

-- 2. Seed with the exact pre-migration cognitive_roles_role_check vocabulary
--    (11 cognitive + 3 actor), so every historical assigned_role value
--    resolves.
INSERT INTO core.task_assignee_roles (role, kind) VALUES
    ('Architect', 'cognitive'),
    ('AutonomousDeveloper', 'actor'),
    ('CapabilityTagger', 'cognitive'),
    ('CodeReviewer', 'cognitive'),
    ('Coder', 'cognitive'),
    ('ConstitutionalCoherenceAnalyst', 'cognitive'),
    ('DocstringWriter', 'cognitive'),
    ('Human', 'actor'),
    ('LocalCoder', 'cognitive'),
    ('LocalReasoner', 'cognitive'),
    ('Planner', 'cognitive'),
    ('RemoteCoder', 'cognitive'),
    ('StrategicAuditor', 'actor'),
    ('Vectorizer', 'cognitive')
ON CONFLICT (role) DO NOTHING;

-- 3. New FK: core.tasks.assigned_role -> core.task_assignee_roles(role).
ALTER TABLE core.tasks
    ADD CONSTRAINT tasks_assigned_role_registry_fkey
    FOREIGN KEY (assigned_role) REFERENCES core.task_assignee_roles(role)
    ON UPDATE CASCADE ON DELETE RESTRICT;

-- 4. Drop the old FK to cognitive_roles (must precede step 5's deletes).
--    IF EXISTS: environments whose cognitive_roles/tasks shape has already
--    drifted from the checked-in schema.sql (e.g. a stale core_test never
--    rebuilt since an earlier baseline) may not carry this exact constraint
--    name -- the goal (no FK from tasks to cognitive_roles) still holds
--    either way, and the ledger, not this file, is what prevents re-running
--    against an environment that's already current.
ALTER TABLE core.tasks
    DROP CONSTRAINT IF EXISTS tasks_assigned_role_fkey;

-- 5. Remove the 3 actor rows from cognitive_roles; shrink its CHECK to the
--    11 real LLM-routed roles.
DELETE FROM core.cognitive_roles
WHERE role IN ('AutonomousDeveloper', 'Human', 'StrategicAuditor');

ALTER TABLE core.cognitive_roles
    DROP CONSTRAINT IF EXISTS cognitive_roles_role_check;

ALTER TABLE core.cognitive_roles
    ADD CONSTRAINT cognitive_roles_role_check
    CHECK (role = ANY (ARRAY[
        'Architect', 'CapabilityTagger', 'CodeReviewer', 'Coder',
        'ConstitutionalCoherenceAnalyst', 'DocstringWriter', 'LocalCoder',
        'LocalReasoner', 'Planner', 'RemoteCoder', 'Vectorizer'
    ]::text[]));

-- 6. Repoint core.v_agent_workload to the full assignable-role universe.
--    DROP + CREATE, not CREATE OR REPLACE: Postgres requires an identical
--    column set for REPLACE, and a drifted environment's prior view may not
--    match this file's exact column list.
DROP VIEW IF EXISTS core.v_agent_workload;

CREATE VIEW core.v_agent_workload AS
 SELECT tar.role,
    COALESCE(cr.is_active, tar.is_active) AS is_active,
    count(t.id) FILTER (WHERE (t.status = 'executing'::text)) AS active_tasks,
    count(t.id) FILTER (WHERE (t.status = 'pending'::text)) AS queued_tasks,
    count(t.id) FILTER (WHERE (t.status = 'blocked'::text)) AS blocked_tasks,
    ( SELECT rra.resource
           FROM core.role_resource_assignments rra
          WHERE ((rra.role = tar.role) AND (rra.is_active = true))
          ORDER BY rra.priority
         LIMIT 1) AS assigned_resource
   FROM ((core.task_assignee_roles tar
     LEFT JOIN core.cognitive_roles cr ON (cr.role = tar.role))
     LEFT JOIN core.tasks t ON (((t.assigned_role = tar.role) AND (t.status = ANY (ARRAY['pending'::text, 'executing'::text, 'blocked'::text])))))
  GROUP BY tar.role, (COALESCE(cr.is_active, tar.is_active))
  ORDER BY tar.role;

-- 7. Self-verify before committing.
DO $$
DECLARE
    leftover_actor_roles INTEGER;
    unresolved_assigned_roles INTEGER;
BEGIN
    SELECT count(*) INTO leftover_actor_roles
    FROM core.cognitive_roles
    WHERE role IN ('AutonomousDeveloper', 'Human', 'StrategicAuditor');
    IF leftover_actor_roles > 0 THEN
        RAISE EXCEPTION '#821 migration failed: % actor role(s) still present in core.cognitive_roles', leftover_actor_roles;
    END IF;

    SELECT count(DISTINCT t.assigned_role) INTO unresolved_assigned_roles
    FROM core.tasks t
    LEFT JOIN core.task_assignee_roles tar ON tar.role = t.assigned_role
    WHERE t.assigned_role IS NOT NULL AND tar.role IS NULL;
    IF unresolved_assigned_roles > 0 THEN
        RAISE EXCEPTION '#821 migration failed: % distinct historical core.tasks.assigned_role value(s) do not resolve in core.task_assignee_roles', unresolved_assigned_roles;
    END IF;

    RAISE NOTICE '#821 Unit 1 migration verified: no actor roles remain in cognitive_roles, all historical assigned_role values resolve.';
END $$;

COMMIT;
