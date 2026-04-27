<!-- path: .specs/state/2026-04-27-test-environment-recon.md -->

# Test environment — current state recon

**Date:** 2026-04-27
**Status:** Investigation
**Method:** Read-only inspection of the repo, the test DB (`core_test`), and the production DB (`core`), driven by two Claude Code investigations on 2026-04-27. Cited inline.
**Scope:** Capture the empirical state of CORE's test environment — schema authority, fixture conventions, CI behavior, and the gaps between them — as the baseline for ADR-016.

---

## 1. Why this recon exists

The 2026-04-27 work on Band B Edge 1 (#164, subsume-path proposal_id linkage) required a new test against `core.blackboard_entries`. The table was missing from `core_test`. The test workaround — an inline `BlackboardEntry.__table__.create(checkfirst=True)` helper — flagged a structural gap: `core_test` does not mirror production, and there is no harness mechanism to make it.

A request for "a shared conftest fixture for blackboard_entries" was the first reflex. The recon revealed the gap is not one missing fixture — it is the absence of a defined test-environment architecture. This document captures what is, so ADR-016 can decide what should be.

---

## 2. Schema authority

No single source of truth governs the test schema today.

- **The SQLAlchemy model registry** (`src/shared/infrastructure/database/models/`) declares some — but not all — production tables. `core.blackboard_entries` and `core.worker_registry` have models (`workers.py:24-101`). `core.proposal_consequences` does not — production has the table, but no ORM declaration exists in the repo.
- **The checked-in schema dump** (`infra/sql/db_schema_live.sql`) is a `pg_dump` snapshot of production. 4773 lines, 47 tables, schema-only, no DROP statements. Last touched 2026-04-04 — 23 days stale at recon time. Hand-refreshed across only 4 commits ever; no automation regenerates it.
- **The migration patches** (`infra/scripts/migrations/*.sql`) are hand-applied raw SQL. Two recent patches (2026-04-26 drop-legacy-proposals, 2026-04-27 approval-authority) are applied to production but not reflected in the dump. No runner; pre-conditions in file headers suggest manual operator workflow.
- **The smoke test** (`tests/test_smoke_db.py:43-46`) references `sql/001_consolidated_schema.sql` — a file that does not exist in the repo. The reset script (`infra/scripts/reset_and_rebuild_db.sh:35`) carries an in-script comment: "The following steps have been performed manually in pgAdmin," and the apply lines are commented out.

Result: production drifts from the dump, the dump drifts from the models, the models drift from production, and no automated reconciliation exists in any direction.

---

## 3. Test database state

`core_test` lives on the same Postgres host as production (`192.168.20.23`, server LIRApg). Both run inside one Postgres instance.

```
Tables in core schema:
  core_test:    28
  core (live):  63
  delta:       -35

Foreign keys:
  core_test:    19
  core (live):  29
  delta:       -10

autonomous_proposals row count:
  core_test:    0
  core (live):  172 (last write 2026-04-27 13:57:52)

Database size:
  core_test:    12 MB
  core (live):  not measured
```

The 35 missing tables include `blackboard_entries`, `worker_registry`, `proposal_consequences`, `audit_findings`, `decision_traces`, `action_results`, `refusals`, `system_health_log`, `knowledge_graph`, several views, and others. `core_test` was loaded once and has been kept current table-by-table only as individual tests began needing tables; it is not a copy of production at any single point in time.

The provisioning mechanism that would close this gap (`infra/scripts/reset_test_db.sh`) has hardcoded credentials (`DB_USER="core"`, `DB_PASS="core"`) that do not match the actual users (`core_db` for live, `core_test_db` for test). The script as committed cannot run.

---

## 4. Fixture conventions

`tests/conftest.py` is 24 lines and contains exactly two fixtures:

```python
@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with get_session() as session:
        yield session

@pytest_asyncio.fixture(autouse=True)
async def _dispose_db_engines_after_each_test() -> AsyncGenerator[None, None]:
    yield
    await dispose_all_engines_for_current_loop_only()
```

No nested `conftest.py` files exist anywhere under `tests/`.

No fixture in the codebase performs schema setup, table creation, seed-data population, or test isolation beyond engine disposal. The `db_session` fixture is function-scoped, has no transactional wrapper, and provides no automatic rollback. Mutating tests clean up by hand in `try/finally`.

A service-registry priming fixture is duplicated verbatim across three test files:

- `tests/will/workers/test_violation_remediator_approval_path.py:28-33`
- `tests/will/workers/test_violation_remediator_finding_ids.py:28-33`
- `tests/will/workers/test_violation_remediator_subsume_proposal_id.py:29-33`

```python
@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    service_registry.prime(get_session)
```

Pattern is trivially extractable; no shared owner.

---

## 5. Transactional rollback is structurally impossible

Code under test commits in its own session, not the test's. `grep` across worker, autonomy, and service paths shows nine commit sites:

- `src/will/workers/proposal_worker.py:195`
- `src/will/workers/test_remediator.py:381`
- `src/will/workers/violation_remediator.py:585`
- `src/will/autonomy/proposal_service.py:126`
- `src/will/autonomy/proposal_state_manager.py:85, 105, 143, 228`
- `src/body/services/blackboard_service.py:712`

Every `BlackboardService` write helper additionally uses `async with session.begin():` — auto-commits on `__aexit__`.

Workers acquire their own sessions via `service_registry.session()`, separate from the test's `db_session`. A `BEGIN ... ROLLBACK` wrapper on the test's session would roll back zero of the writes the system-under-test produces. Two transactions are involved per test: the test's setup/assertion transaction, and the worker's own. Wrapping only the former is theatre.

Conclusion: per-test isolation must come from table-level cleanup (TRUNCATE between tests), not session-level rollback.

---

## 6. CI pipeline

Six workflows under `.github/workflows/`: `ci.yml`, `core-ci.yml`, `daily_sync.yml`, `docs.yml`, `intent-validate.yml`, `nightly-audit.yml`.

`grep -rn "core_test|DATABASE_URL|postgres|pg_" .github/` returned nothing. No workflow provisions Postgres, points at a remote DB, or skips DB-touching tests. `ci.yml` and `core-ci.yml` invoke `pytest` with no DB available.

Implication: tests requiring `192.168.20.23` (the smoke tests at `tests/test_smoke_db.py:32-39` and the three worker tests) cannot reach a database in CI. They either fail silently, error in a way CI does not surface, or the CI run is green for reasons that do not include those tests passing. The recon did not determine which; the answer affects how Band D issues sequence.

---

## 7. Test parallelism and engine lifecycle

Tests run sequentially. `pytest-xdist` is not in `pyproject.toml`. The `parallel = true` flag at `pyproject.toml:248` is under `[tool.coverage.run]` and controls coverage-data parallelism, not pytest worker count. Tests share the single `core_test` database without locking; a parallel run today would race on shared rows.

The autouse `_dispose_db_engines_after_each_test` fixture disposes the loop-local engine cache after every test. Combined with worker code that creates its own session via `service_registry.session()` (which acquires the loop-local engine), this means each test pays the cost of recreating the asyncpg engine. It also means a session that crosses test boundaries would be killed when the engine is disposed. Fine for the current design; constrains any future fixture that wants module or session scope on a DB resource.

---

## 8. Safety asserts

`tests/test_smoke_db.py:27` and `tests/test_smoke_runtime.py:27` assert that `core_test` appears in the active `DATABASE_URL` before any DB-mutating test runs. `pytest-dotenv` (configured at `pyproject.toml:195-196`) loads `.env.test` with `env_override_existing_values = true`. `src/shared/config.py:94-117` separately detects pytest, force-sets `CORE_ENV=TEST`, and re-loads with `override=True`. Belt-and-suspenders.

If precedence ever drifts, the smoke-test asserts are the final catch. The smoke tests themselves are what require `192.168.20.23` reachability — section 6 applies.

---

## 9. Other observations

- **The 0-row state of `core_test`.** `autonomous_proposals` is empty in `core_test` despite the table being present and production carrying 172 rows. There is no seed-data fixture; `core_test` is loaded clean and stays clean only because the per-test `try/finally` cleanup discipline holds. A crash mid-test would leave orphans.

- **`reset_and_rebuild_db.sh` documents its own brokenness.** Line 35: "The following steps have been performed manually in pgAdmin." The script is the documentation of the manual workaround.

- **Smoke test's assertion does not detect the gap.** `tests/test_smoke_db.py:43-60` asserts `count > 0` for tables in the `core` schema. `core_test` has 28 — well above 0. The smoke test is satisfied by any non-empty schema and does not detect the 35 missing tables.

- **The `_ensure_blackboard_table` workaround is unique.** No other test file uses `__table__.create(checkfirst=True)` or `metadata.create_all`. The pattern is a one-off, not part of a convention.

- **LIRApg currently hosts 8 databases**, of which `core` is the only operational one. `core_test` is the active test target. Five others (`DeepSeek_LIRA_db`, `LIRA_DB_Gemini`, `lira_db_test`, `lira_test_validation`, `postgres`) are dormant. Cleanup opportunity, not a recon-relevant fact for the test environment.

---

## 10. Summary

The test environment is not architected. Each gap surfaced in this recon — missing tables, stale dump, broken reset script, duplicated fixture, no CI Postgres, ad-hoc workarounds — is a symptom of the absence of a deliberate design. The artifacts that suggest an intent (the smoke test's reference to a non-existent SQL file, the commented-out apply step in the reset script, the per-table accumulation in `core_test`) describe a workflow that was once partially designed and has since decayed.

The current state holds because the convention "drop and recreate when something breaks, work around what doesn't" has been workable at CORE's scale. Band B's verification claims (URS Q1.F, Q2.F, etc.) and Band D's broader engine-integrity work require a stronger guarantee than that. The next decision is ADR-016: design the test environment from scratch.

---

## References

- Recon source 1 (test-env mapping, 2026-04-27): test DB lifecycle, fixtures, `core.*` coverage, tests that touch `blackboard_entries`.
- Recon source 2 (deeper recon, 2026-04-27): `db_schema_live.sql` properties and generation, raw-SQL patches, CI pipeline, `core_test` contents, commit semantics, fixture conventions.
- `infra/sql/db_schema_live.sql` — pg_dump, 2026-04-04, 4773 lines.
- `infra/scripts/reset_test_db.sh` — broken credentials.
- `infra/scripts/reset_and_rebuild_db.sh` — apply step commented out, manual workaround documented in script.
- `infra/scripts/migrations/20260426_drop_legacy_proposals.sql`.
- `infra/scripts/migrations/20260427_add_approval_authority_to_autonomous_proposals.sql`.
- `tests/conftest.py` — 24 lines.
- `tests/test_smoke_db.py:43-46` — references non-existent `sql/001_consolidated_schema.sql`.
- `src/shared/infrastructure/database/models/workers.py` — `BlackboardEntry`, `WorkerRegistry` models.
- ADR-016 (forthcoming) — decision based on this recon.
