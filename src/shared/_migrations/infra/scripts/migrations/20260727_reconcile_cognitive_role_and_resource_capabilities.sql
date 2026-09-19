-- 20260727_reconcile_cognitive_role_and_resource_capabilities.sql
--
-- Reconciles core.cognitive_roles.required_capabilities and
-- core.llm_resources.provided_capabilities against the canonical
-- capability taxonomy (.intent/taxonomies/capability_taxonomy.yaml),
-- closing the drift flagged by capability.taxonomy.roles_require_canonical_
-- capabilities / capability.taxonomy.resources_provide_canonical_capabilities
-- (#821).
--
-- Role side (3 roles, 4 non-canonical values): pure data transcription of
-- the governor-specified mapping already recorded in commit 674a20f0, which
-- canonicalized .intent/taxonomies/cognitive_roles.yaml on 2026-07-21 but
-- deliberately left core.cognitive_roles untouched pending a projection
-- mechanism (no new interpretation here):
--   ConstitutionalCoherenceAnalyst: long_context_reasoning -> reasoning, analysis
--                                    structured_output      -> json_output, schema_compliance
--   DocstringWriter:                documentation           -> code_generation (code_understanding retained)
--   LocalReasoner:                  yaml_analysis           -> analysis, document_parsing (reasoning retained)
--
-- Resource side (ollama_reasoner, 2 non-canonical values): core.llm_resources
-- has no YAML source of truth (ADR-052 SS1: the table is the SSOT) and no
-- authoring surface, so there is no prior decision to transcribe here.
-- yaml_analysis mirrors the same translation used on the role side for
-- consistency. text_generation does not correspond to any family in the
-- canonical taxonomy (reasoning/code/structured_output/retrieval/perception)
-- -- dropped rather than inventing a new canonical capability. Zero
-- operational risk: ollama_reasoner is currently is_available=false and all
-- 3 of its role_resource_assignments rows are is_active=false (verified
-- 2026-07-27).
--
-- Idempotent: each statement sets an absolute value, safe to re-run.

BEGIN;

UPDATE core.cognitive_roles
SET required_capabilities = '["reasoning", "analysis", "json_output", "schema_compliance"]'::jsonb
WHERE role = 'ConstitutionalCoherenceAnalyst';

UPDATE core.cognitive_roles
SET required_capabilities = '["code_generation", "code_understanding"]'::jsonb
WHERE role = 'DocstringWriter';

UPDATE core.cognitive_roles
SET required_capabilities = '["reasoning", "analysis", "document_parsing"]'::jsonb
WHERE role = 'LocalReasoner';

UPDATE core.llm_resources
SET provided_capabilities = '["reasoning", "analysis", "document_parsing"]'::jsonb
WHERE name = 'ollama_reasoner';

COMMIT;
