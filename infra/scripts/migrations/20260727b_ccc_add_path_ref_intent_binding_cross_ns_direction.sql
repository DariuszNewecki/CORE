-- 20260727b_ccc_add_path_ref_intent_binding_cross_ns_direction.sql
--
-- Extends core.coherence_candidates_relation_check to accept the three CCC
-- check classes added by f01199d8 ("feat(ccc): add PATH_REF and
-- INTENT_BINDING check classes (#622, #623)") plus CROSS_NS_DIRECTION
-- (#477): PATH_REF, INTENT_BINDING, CROSS_NS_DIRECTION.
--
-- ADR-073 D9 already specified this exact evolution ("ADD the new codes...
-- to the CHECK constraint") for the check-class taxonomy it introduced;
-- f01199d8 added the scanner code (src/mind/coherence/checks/path_ref.py,
-- intent_binding.py, cross_ns_direction.py, each declaring its own
-- `relation` class attribute) but never shipped the matching schema
-- migration. Any `core-admin coherence check --full` run that reaches one
-- of these three classes fails with a CheckViolationError on INSERT,
-- discovered live on 2026-07-27 (a full scan had not been run since the
-- code landed). Filed as a follow-up issue alongside this migration.
--
-- Idempotent: DROP/ADD of the same named constraint is safe to re-run.

BEGIN;

ALTER TABLE core.coherence_candidates
    DROP CONSTRAINT coherence_candidates_relation_check;

ALTER TABLE core.coherence_candidates
    ADD CONSTRAINT coherence_candidates_relation_check
    CHECK (relation = ANY (ARRAY[
        'R1_SCOPED', 'SAMECONCERN', 'ROW2_GROUNDING', 'ROW3_CITATION',
        'ROW4_NAMING', 'SPECGAP', 'VOCABULARY', 'R1', 'R2', 'R3', 'R4',
        'DISPATCH_PARITY', 'PATH_REF', 'INTENT_BINDING', 'CROSS_NS_DIRECTION'
    ]::text[]));

COMMIT;
