-- 20260512_remove_orphan_repo_embedder_registry_row.sql
--
-- Removes the orphan core.worker_registry row carrying the pre-rotation
-- placeholder UUID for the Repo Embedder worker.
--
-- BACKGROUND
--
-- On 2026-03-14 the RepoEmbedderWorker was first registered with the
-- placeholder UUID 'a2b3c4d5-e6f7-8901-bcde-f12345678902' declared in
-- .intent/workers/repo_embedder.yaml (commit 01a112fc). On 2026-05-12 commit
-- a52a6453 ("fix(intent): rotate placeholder UUIDs out of worker declarations
-- and symbol IDs") replaced that placeholder with the real UUID
-- 'c30a50fa-a761-4013-8088-a7b45d29f3e0'. The next daemon restart registered
-- the new UUID; the old row remained behind as an orphan, last_heartbeat
-- frozen at 2026-05-12 14:32 — permanently DEAD by any naive
-- now() - last_heartbeat test, even though no worker is actually silent.
--
-- ADR-041 D3 already silences orphan rows in liveness reads, so this row
-- raises no false 'worker.silent' findings. The row is removed here only to
-- restore registry hygiene — a single Repo Embedder row instead of two —
-- and to stop polluting dashboards that show every registry row regardless
-- of orphan status.
--
-- RE-ATTRIBUTION, NOT DELETION, OF FK CHILDREN
--
-- Unlike 20260503_retire_vector_sync_worker.sql (which deleted the worker's
-- blackboard history because no canonical successor existed), this migration
-- KEEPS the orphan's 281 blackboard entries by re-attributing them to the
-- live UUID. Both rows represent the same logical worker (identical
-- worker_name, worker_class, phase); they differ only in the placeholder-
-- versus-rotated UUID. Re-attribution preserves the audit history (238
-- worker.heartbeat + 43 repo.embed.complete entries) under the canonical
-- identity and satisfies the FK constraint
-- blackboard_entries_worker_uuid_fkey before the orphan row can be deleted.
--
-- INVARIANT: post-migration there is exactly one core.worker_registry row
-- with worker_name='Repo Embedder', carrying worker_uuid=
-- 'c30a50fa-a761-4013-8088-a7b45d29f3e0', and zero rows referencing the
-- placeholder UUID anywhere.
--
-- Forward-only. No rollback. Re-running is a safe no-op — the UPDATE
-- matches zero rows and the DELETE matches zero rows once the migration
-- has been applied.

BEGIN;

UPDATE core.blackboard_entries
   SET worker_uuid = 'c30a50fa-a761-4013-8088-a7b45d29f3e0'
 WHERE worker_uuid = 'a2b3c4d5-e6f7-8901-bcde-f12345678902';

DELETE FROM core.worker_registry
 WHERE worker_uuid = 'a2b3c4d5-e6f7-8901-bcde-f12345678902';

-- Verification: orphan UUID must be absent from both tables, and exactly
-- one Repo Embedder row must remain in the registry.
SELECT count(*) AS remaining_orphan_registry_rows
FROM core.worker_registry
WHERE worker_uuid = 'a2b3c4d5-e6f7-8901-bcde-f12345678902';

SELECT count(*) AS remaining_orphan_blackboard_entries
FROM core.blackboard_entries
WHERE worker_uuid = 'a2b3c4d5-e6f7-8901-bcde-f12345678902';

SELECT count(*) AS repo_embedder_registry_rows
FROM core.worker_registry
WHERE worker_name = 'Repo Embedder';

COMMIT;
