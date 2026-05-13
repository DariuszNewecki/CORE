-- 20260513_create_llm_gate_verdicts.sql
--
-- Creates core.llm_gate_verdicts — the incremental verdict cache for
-- llm_gate rule evaluations introduced in ADR-044.
--
-- BACKGROUND
--
-- Every audit run currently re-evaluates each llm_gate rule against its
-- full pre-selected file set, regardless of whether the file or the rule
-- has changed since the last evaluation. On a stable codebase this pays
-- the LLM cost repeatedly for zero informational gain. The dominant
-- offender today is purity.docstrings.required (~80 files, ~6 min per
-- full audit on warm qwen2.5-coder:3b).
--
-- ADR-044 introduces a content-hash + rule-hash keyed verdict cache:
-- before dispatching a (rule, file) pair to Ollama, the llm_gate engine
-- looks up an existing verdict; on a cache hit the stored findings are
-- returned without an LLM call. Cache key includes the rule's
-- canonicalised YAML hash, so meaningful prompt or threshold edits
-- invalidate the affected rows automatically.
--
-- SCHEMA
--
-- llm_gate_verdicts(
--     id                  UUID    PK,
--     rule_id             TEXT    NOT NULL,
--     file_path           TEXT    NOT NULL,
--     file_content_hash   TEXT    NOT NULL,      -- mirrors repo_artifacts.content_hash
--     rule_content_hash   TEXT    NOT NULL,      -- SHA-256 of canonical rule YAML
--     verdict             TEXT    NOT NULL,      -- PASS | FAIL | ERROR
--     findings_json       JSONB   NOT NULL,      -- serialised list of findings
--     evaluated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
-- );
--
-- Constraints:
--   * UNIQUE (rule_id, file_path, file_content_hash, rule_content_hash)
--     — the cache key. Upsert target. A change in either hash produces a
--     new row rather than overwriting in place; TTL sweep handles
--     accumulation of historical verdicts.
--   * CHECK (verdict IN ('PASS','FAIL','ERROR'))
--     — closed set per ADR-044 §Decision; mirrors how other status-like
--     enums in core are guarded by structural CHECK rather than PG ENUM.
--
-- Indexes:
--   * llm_gate_verdicts_rule_file_idx — covers the engine's hot lookup
--     pattern (rule_id, file_path), which is also the cleanup pattern
--     (delete-by-file when RepoCrawlerWorker detects a removed path).
--
-- INVALIDATION SURFACES
--
--   * File content change         → file_content_hash differs → miss → new row
--   * Rule YAML change            → rule_content_hash differs → miss → new row
--   * File deletion (crawler)     → RepoCrawlerWorker DELETEs matching rows
--   * Age-based eviction          → llm_gate engine TTL sweep at audit start,
--                                   governed by operational_config.
--                                   llm_gate_verdict_cache_ttl_days
--   * --force-llm                 → skip cache READ, still write
--
-- FORWARD-ONLY. No rollback. Re-running is a safe no-op — every DDL
-- statement uses an IF (NOT) EXISTS guard. Per ADR-015 D7.
--
-- References:
--   * ADR-044 — incremental LLM-gate verdict cache (this migration)
--   * ADR-043 — pre-selector throughput intervention (preceding work)
--   * ADR-039 — audit-input cache invalidation (the per-cycle equivalent)
--   * core.repo_artifacts.content_hash — sibling change-detection surface

BEGIN;

CREATE TABLE IF NOT EXISTS core.llm_gate_verdicts (
    id                UUID NOT NULL DEFAULT gen_random_uuid(),
    rule_id           TEXT NOT NULL,
    file_path         TEXT NOT NULL,
    file_content_hash TEXT NOT NULL,
    rule_content_hash TEXT NOT NULL,
    verdict           TEXT NOT NULL,
    findings_json     JSONB NOT NULL,
    evaluated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT llm_gate_verdicts_pkey PRIMARY KEY (id),
    CONSTRAINT llm_gate_verdicts_verdict_chk
        CHECK (verdict IN ('PASS', 'FAIL', 'ERROR')),
    CONSTRAINT llm_gate_verdicts_cache_key_unique
        UNIQUE (rule_id, file_path, file_content_hash, rule_content_hash)
);

CREATE INDEX IF NOT EXISTS llm_gate_verdicts_rule_file_idx
    ON core.llm_gate_verdicts (rule_id, file_path);

-- Verification: structure is as declared.
SELECT
    count(*) FILTER (WHERE column_name = 'rule_id') AS has_rule_id,
    count(*) FILTER (WHERE column_name = 'file_path') AS has_file_path,
    count(*) FILTER (WHERE column_name = 'file_content_hash') AS has_file_content_hash,
    count(*) FILTER (WHERE column_name = 'rule_content_hash') AS has_rule_content_hash,
    count(*) FILTER (WHERE column_name = 'verdict') AS has_verdict,
    count(*) FILTER (WHERE column_name = 'findings_json') AS has_findings_json,
    count(*) FILTER (WHERE column_name = 'evaluated_at') AS has_evaluated_at
FROM information_schema.columns
WHERE table_schema = 'core'
  AND table_name = 'llm_gate_verdicts';

COMMIT;
