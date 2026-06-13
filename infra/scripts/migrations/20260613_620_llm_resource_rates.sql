-- #620: llm_exchange_log.cost_estimate hardcoded to None — populate cost.
-- Date: 2026-06-13
--
-- The only writer (shared.infrastructure.llm.client._log_exchange) set
-- cost_estimate=None on every row, so 0 of ~35,669 rows carried a cost.
-- This migration adds the rate source the writer now reads.
--
-- Rates are keyed on model_snapshot (the model recorded per exchange row),
-- not resource_name: pricing is a property of the model, and model_snapshot
-- survives a resource being re-pointed at a different model. The composite
-- PK (model_snapshot, effective_from) makes the table append-only — a price
-- change inserts a new row and historical exchange rows price at the rate
-- active at their ts.
--
-- Seed rates (verified 2026-06-13):
--   deepseek-chat       $0.14 in / $0.28 out per Mtok  (deepseek-v4-flash
--                       non-thinking; cache pricing out of scope per #620)
--   claude-sonnet-4-6   $3.00 in / $15.00 out per Mtok (base, non-cache)
--   local Ollama models 0 / 0
--
-- APPROXIMATION (governor-confirmed, #620): effective_from is 2026-01-01 for
-- every seed row, before the earliest data (2026-05-23). DeepSeek changed
-- deepseek-chat pricing within the data window; the older deepseek rows are
-- therefore priced at the current rate. To attribute precisely later, insert
-- an earlier-dated deepseek-chat rate row — the writer and backfill both
-- honour the greatest effective_from <= ts. Sonnet rows are all 2026-06-09,
-- so today's rate is exact for them.
--
-- The dormant core.llm_resources.cost_per_token column (NULL on all rows,
-- read by no business logic) is left untouched and superseded by this table;
-- its retirement is a separate follow-up.

BEGIN;

CREATE TABLE core.llm_resource_rates (
    model_snapshot  text NOT NULL,
    input_per_mtok  numeric(12,6) NOT NULL,
    output_per_mtok numeric(12,6) NOT NULL,
    effective_from  timestamp with time zone NOT NULL,
    CONSTRAINT llm_resource_rates_pkey PRIMARY KEY (model_snapshot, effective_from)
);

ALTER TABLE core.llm_resource_rates OWNER TO core_db;

COMMENT ON TABLE core.llm_resource_rates IS
    'Append-only per-model LLM pricing (USD per million tokens), keyed on '
    'model_snapshot. Cost = (prompt_tokens*input_per_mtok + '
    'completion_tokens*output_per_mtok)/1e6 at the greatest '
    'effective_from <= the exchange row''s ts. See #620.';

INSERT INTO core.llm_resource_rates
    (model_snapshot, input_per_mtok, output_per_mtok, effective_from)
VALUES
    ('deepseek-chat',       0.140000,  0.280000, '2026-01-01 00:00:00+00'),
    ('claude-sonnet-4-6',   3.000000, 15.000000, '2026-01-01 00:00:00+00'),
    ('nomic-embed-text-8k', 0.000000,  0.000000, '2026-01-01 00:00:00+00'),
    ('qwen2.5-coder:3b',    0.000000,  0.000000, '2026-01-01 00:00:00+00'),
    ('qwen2.5:7b',          0.000000,  0.000000, '2026-01-01 00:00:00+00');

-- Backfill existing rows. UPDATE on the partition parent propagates to every
-- monthly partition. Only rows whose model has a covering rate are touched;
-- any unpriced model stays NULL (visible gap, matching the writer fallback).
UPDATE core.llm_exchange_log AS l
SET cost_estimate = (
        COALESCE(l.prompt_tokens, 0) * (
            SELECT rr.input_per_mtok
            FROM core.llm_resource_rates rr
            WHERE rr.model_snapshot = l.model_snapshot
              AND rr.effective_from <= l.ts
            ORDER BY rr.effective_from DESC
            LIMIT 1)
      + COALESCE(l.completion_tokens, 0) * (
            SELECT rr.output_per_mtok
            FROM core.llm_resource_rates rr
            WHERE rr.model_snapshot = l.model_snapshot
              AND rr.effective_from <= l.ts
            ORDER BY rr.effective_from DESC
            LIMIT 1)
    ) / 1000000
WHERE EXISTS (
        SELECT 1
        FROM core.llm_resource_rates rr
        WHERE rr.model_snapshot = l.model_snapshot
          AND rr.effective_from <= l.ts);

COMMIT;
