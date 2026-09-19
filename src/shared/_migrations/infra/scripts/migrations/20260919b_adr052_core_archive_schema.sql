-- 20260919b_adr052_core_archive_schema.sql
--
-- ADR-162 U5a — historical reconstruction (backfill).
--
-- Origin: ADR-052 (LLM exchange log retention). The partition archiver
-- (`log.archive_partitions`, src/body/atomic/log_actions.py, commit ca0163db,
-- 2026-07-05, #330) creates `core_archive` at runtime ("CREATE SCHEMA IF NOT
-- EXISTS") and detaches old llm_exchange_log partitions into it. The live
-- database acquired the schema that way; schema.sql captured it when it was
-- regenerated from live (5c67d37d, 2026-08-30). No migration file existed, so a
-- v2.9.1 database upgraded through the manifest lacked it (found by the
-- hop-equivalence test, ADR-162 U5).
--
-- Structure only; the schema is empty until the archiver moves partitions.
-- Idempotent; one transaction (leading BEGIN / trailing COMMIT are stripped by
-- the engine, kept for `psql -f` readability).

BEGIN;

CREATE SCHEMA IF NOT EXISTS core_archive;

COMMIT;
