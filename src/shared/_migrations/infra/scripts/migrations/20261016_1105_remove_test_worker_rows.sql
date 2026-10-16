-- 20261016_1105_remove_test_worker_rows.sql
--
-- Removes the 19 core.worker_registry rows that integration tests wrote into
-- the production database on 2026-06-07 (13:16-14:40 UTC), and the blackboard
-- entries attributed to them (#1105).
--
-- BACKGROUND
--
-- That day Settings.__init__ loaded .env with load_dotenv(override=True), which
-- overwrote pytest's CORE_ENV=TEST, so the suite read .env, not .env.test, and
-- its DATABASE_URL named the live `core` database (#592, fixed by 9c181406 the
-- same day at 15:25 UTC). Since #941 (eb585a9c, 2026-10-04) integration tests
-- refuse to run unless the database is exactly `core_test`.
--
-- The rows are test registrations, not workers: no declaration in
-- .intent/workers/ names them, and their last heartbeats are 2026-06-07.
-- Their blackboard entries are test data too, so they are deleted, not
-- re-attributed (blackboard_entries_worker_uuid_fkey requires one or the
-- other before the registry rows can go).
--
-- Forward-only. Re-running is a no-op: both DELETEs then match zero rows.

BEGIN;

DELETE FROM core.blackboard_entries
 WHERE worker_uuid IN (
    'f063a4e2-5dbd-4274-987a-2d427ddbb2d7', -- test.d8.synthetic
    '0bc1c93a-9888-4bf8-a247-c84eab4926ab', -- test.d8.synthetic
    'b3322b67-cdea-4cfc-ad98-71603d4796e4', -- test.d8.synthetic
    '4d9b9057-e2c7-47d2-ba80-e97acd8e5cb8', -- test.d8.synthetic
    '4c29ca69-6b30-4cd3-8a32-6acb35d6ae5b', -- test.d8.synthetic
    'fce8a610-56c8-4262-8c8e-76c6f743bb26', -- test.d8.synthetic
    '70ec676d-c090-4107-b54a-5428bcd536d8', -- test.d8.synthetic
    'ac5856b4-8189-4a5e-8b25-c9bd2e04a749', -- test_worker_ac5856b4
    '84c56291-d60c-40d8-b320-e977d76e5cf0', -- test_worker_84c56291
    'b5cfec97-7645-4595-896c-7c0a9dc88702', -- test_worker_b5cfec97
    'ddc881ae-a061-4eac-9bd1-8cfc127f45ed', -- test_worker_ddc881ae
    '576be5e9-73e7-4a3c-b52f-3666b0c648e7', -- test_worker_576be5e9
    '431a0f7e-389d-469e-bec2-631ac03e94d1', -- test_worker_431a0f7e
    '3c3592f8-bcab-4764-83fa-99a380fd8b26', -- test_worker_3c3592f8
    'd2fdb46c-53b3-400b-8516-ed3c35197e10', -- test_worker_d2fdb46c
    'b244f641-2345-413f-b252-23dff374300a', -- test_reject_revives_b244f641
    '0993fbea-2b08-4a90-933d-b06166e337d0', -- test_reject_revives_0993fbea
    'a98e4dd0-25db-4eb8-84a1-a00cf5c52832', -- test_reject_revives_a98e4dd0
    'a6394ac9-e816-40bc-8b1f-1790133d996a'  -- test_reject_revives_a6394ac9
 );

DELETE FROM core.worker_registry
 WHERE worker_uuid IN (
    'f063a4e2-5dbd-4274-987a-2d427ddbb2d7',
    '0bc1c93a-9888-4bf8-a247-c84eab4926ab',
    'b3322b67-cdea-4cfc-ad98-71603d4796e4',
    '4d9b9057-e2c7-47d2-ba80-e97acd8e5cb8',
    '4c29ca69-6b30-4cd3-8a32-6acb35d6ae5b',
    'fce8a610-56c8-4262-8c8e-76c6f743bb26',
    '70ec676d-c090-4107-b54a-5428bcd536d8',
    'ac5856b4-8189-4a5e-8b25-c9bd2e04a749',
    '84c56291-d60c-40d8-b320-e977d76e5cf0',
    'b5cfec97-7645-4595-896c-7c0a9dc88702',
    'ddc881ae-a061-4eac-9bd1-8cfc127f45ed',
    '576be5e9-73e7-4a3c-b52f-3666b0c648e7',
    '431a0f7e-389d-469e-bec2-631ac03e94d1',
    '3c3592f8-bcab-4764-83fa-99a380fd8b26',
    'd2fdb46c-53b3-400b-8516-ed3c35197e10',
    'b244f641-2345-413f-b252-23dff374300a',
    '0993fbea-2b08-4a90-933d-b06166e337d0',
    'a98e4dd0-25db-4eb8-84a1-a00cf5c52832',
    'a6394ac9-e816-40bc-8b1f-1790133d996a'
 );

COMMIT;
