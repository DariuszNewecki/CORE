<!-- path: .specs/decisions/ADR-016-test-environment-architecture.md -->

# ADR-016: Test environment architecture

**Status:** Accepted
**Date:** 2026-04-27
**Authors:** Darek (Dariusz Newecki)
**Reconnaissance:** `.specs/state/2026-04-27-test-environment-recon.md`

## Context

CORE's test environment was not designed; it accreted. The 2026-04-27 recon (linked above) found:

- `core_test` has 28 tables; production has 63. The 35 missing include `blackboard_entries`, `worker_registry`, `proposal_consequences`, `audit_findings`, `decision_traces`, several views.
- The intended schema-apply mechanism (`tests/test_smoke_db.py:43-46` references `sql/001_consolidated_schema.sql`) does not exist in the repo. The reset script (`infra/scripts/reset_and_rebuild_db.sh:35`) carries an in-script comment that the apply step "has been performed manually in pgAdmin."
- `infra/sql/db_schema_live.sql` is a hand-refreshed pg_dump, 23 days stale at recon time, missing two production patches landed in the past 48 hours.
- `infra/scripts/reset_test_db.sh` has hardcoded credentials that do not match the actual users; the script as committed cannot run.
- `tests/conftest.py` is 24 lines, contains no schema setup, no isolation, no service-registry priming. `_prime_service_registry` is duplicated verbatim across three worker test files.
- Worker code under test commits in its own session via `service_registry.session()`, separate from the test's `db_session`. Transactional rollback wrapping the test session would roll back zero of the writes the system-under-test produces. Per-test isolation must come from table-level cleanup, not session-level rollback.
- CI runs `pytest` with no Postgres provisioned, no service container, no remote DB. DB-touching tests cannot reach a database when CI runs them.

The current state holds because workarounds suffice at CORE's scale. Band B's verification claims (URS Q1.F, Q2.F, etc.) and Band D's engine-integrity work require a test environment that is reproducible, faithful to production schema, and CI-functional. This ADR makes the architecture deliberate.

## Decision

Four coordinated sub-decisions.

### D1 — Schema authority: the SQLAlchemy model registry

The model registry at `src/shared/infrastructure/database/models/` is the single source of truth for the test schema. Tests build the schema from models via `Base.metadata.create_all`. Production reconciles toward the models, not the reverse.

This inverts the current direction of drift. When production has a column or table the models lack, that becomes a model to add (or a migration to write), not a dump to manually refresh.

**Prerequisite:** the model registry must be complete. Recon identified one known gap — `core.proposal_consequences` exists in production but has no SQLAlchemy model. Adding the model is a precondition for D1 to produce a faithful schema; tracked as a Band D issue.

**Constraint not closed by D1:** Postgres-side constructs that do not live naturally in SQLAlchemy models (CHECK constraints, triggers, materialized-view definitions, partial indexes). The 2026-04-27 `approval_authority` CHECK from ADR-015 D2 is an example. Two acceptable shapes:
- declared via SQLAlchemy `CheckConstraint` on the model where possible;
- maintained as `infra/sql/post_create_overlay.sql`, applied immediately after `create_all` in the conftest fixture.

The choice is per-construct and made at construct-introduction time, not by this ADR.

### D2 — Test DB lifecycle: ephemeral `core_test` per pytest session

The test DB is recreated at the start of each pytest session and not preserved between sessions:

```
1. Connect to LIRApg as a role with CREATEDB privilege.
2. DROP DATABASE IF EXISTS core_test.
3. CREATE DATABASE core_test.
4. Connect to fresh core_test.
5. Base.metadata.create_all() to apply full schema.
6. (If overlay exists) apply infra/sql/post_create_overlay.sql.
7. service_registry.prime(get_session).
8. Hand off to tests.
```

Wired as a session-scoped autouse fixture in `tests/conftest.py`. The existing function-scoped `db_session` fixture continues to yield sessions against this DB.

The session-end teardown drops `core_test` or leaves it for the next session to drop. Either is acceptable; leaving it preserves a useful artifact for post-failure inspection without affecting correctness.

### D3 — Per-test isolation: TRUNCATE CASCADE between tests

A function-scoped autouse fixture runs `TRUNCATE TABLE core.<every_table> CASCADE` between tests. Indifferent to which session committed the rows (worker or test). Microsecond-scale on empty tables. No `try/finally` cleanup in test bodies needed.

The recon (§5) established that transactional rollback is structurally impossible: workers commit in their own sessions outside the test's transaction. TRUNCATE works at the table level, sidestepping session ownership entirely.

### D4 — CI: GitHub Actions Postgres service container

CI workflows that run DB-touching tests provision a Postgres service container alongside the job. Tests connect via `DATABASE_URL` set to the container's address. The same conftest fixture (D2) operates against the container; the conftest does not know it is in CI.

This makes local and CI execute identical code paths against equivalent DBs. The recon found that current CI cannot reach `192.168.20.23` and is therefore not running DB tests at all (or running them and failing in unsurfaced ways). D4 closes that gap.

## Consequences

### Positive

- Test schema becomes faithful to production by construction. The `_ensure_blackboard_table` workaround retires. Future tests that need missing tables (`worker_registry`, `proposal_consequences`, etc.) get them automatically.
- Test execution is reproducible. Every pytest run starts from an identical clean DB; state from prior runs cannot leak. Orphan rows from crashed prior tests cannot accumulate in `core_test` between sessions.
- CI runs DB tests against a real Postgres. The verification claims that depend on those tests (Band B URS queries, future Band D work) gain CI coverage.
- One code path for local and CI. The conftest is environment-agnostic; `DATABASE_URL` is the only thing that differs.
- Several existing artifacts retire: `infra/sql/db_schema_live.sql` (stale dump), `infra/scripts/reset_test_db.sh` (broken script), `infra/scripts/reset_and_rebuild_db.sh` (manual workaround documented in code). The raw-SQL migration patches under `infra/scripts/migrations/` retire as production reconciles toward the models, on a separate timeline.
- `_prime_service_registry` promotes to top-level `tests/conftest.py`, eliminating the 3x duplication.

### Negative

- D1 forces a question this ADR does not answer: how does production schema converge on the model registry over time? Production has 172 rows in `autonomous_proposals` and tables (`proposal_consequences`) without models. `create_all` does not work against a populated DB. A production-migration story (Alembic baseline, hand-written ALTERs, or rebuild-from-models) becomes necessary. **Out of scope for this ADR; flagged as a follow-up requiring its own decision.**
- The `infra/sql/post_create_overlay.sql` mechanism (when needed) introduces a second place where schema lives. Acceptable for constructs that do not fit cleanly in SQLAlchemy, but every overlay item is a small drift surface. Mitigated by keeping the overlay minimal — model-first, overlay-only-where-required.
- CI run time grows by the time it takes to spin up a Postgres service container per job. GitHub-hosted runners typically incur ~10s for this; on the order of test-suite latency it is noise, but it is not zero.
- TRUNCATE CASCADE on every test means the per-test cost is a transaction against every table in `core`. With 63+ tables, this is small but non-zero. Will scale linearly with table count. If test counts grow significantly, may warrant scoping the truncate list to only tables the test could plausibly have written to.
- The model registry must stay complete. Any production table without a model becomes invisible to the test environment. Adds discipline at table-introduction time; the missing `proposal_consequences` model demonstrates the discipline has not been enforced to date.

### Neutral

- `core_test` continues to live on LIRApg alongside production `core`. No new infrastructure on the dev machine.
- The five dormant `*_test` / `*_db_*` databases on LIRApg outside `core_test` are out of scope. Their disposition (cleanup, retire, ignore) is not affected by this decision.
- Test parallelism is unchanged. `pytest-xdist` is not adopted by this ADR; per-session ephemeral DB scopes naturally to serial execution. Adopting xdist later would require per-worker DBs (e.g., `core_test_<worker_id>`), which is a future decision.

## Alternatives considered

### For D1 — schema authority

**Production as authority (`pg_dump` per session).** Rejected. Couples test execution to production reachability. Encodes production drift into tests. Means a column dropped from production breaks tests for reasons unrelated to the change under test. Reverses the direction of drift in the wrong direction.

**Hand-curated SQL file (`sql/001_consolidated_schema.sql`).** Rejected. This is what `tests/test_smoke_db.py:43-46` already references and what does not exist. The recon shows hand-curated dumps decay; `db_schema_live.sql` is the existence proof.

**Alembic with baseline migration matching production.** Rejected as the *test environment* authority. May still be the right answer for *production migration* (the question D1 surfaces but does not answer). For the test environment specifically, Alembic adds ceremony — every test run replays migration history — without solving a problem `create_all` does not solve.

### For D2 — test DB lifecycle

**Keep stable `core_test`, repair its schema once.** Rejected. The recon shows this is the current state and it has decayed. A one-time repair without a mechanism to keep it current produces the same gap in N months.

**Docker container per session via testcontainers.** Rejected as overkill. CORE has Postgres on the same host. Adding Docker introduces a tool dependency for a problem solvable with a `DROP DATABASE; CREATE DATABASE` cycle.

**Schema applied once at developer-machine setup, not per session.** Rejected. Schema drifts when models change; a setup-time apply means every model change requires re-running setup. Per-session is cheap and self-correcting.

### For D3 — per-test isolation

**Transactional rollback wrapping `db_session`.** Rejected on structural grounds (recon §5). Workers commit in their own sessions; rollback wrapping the test session is theatre.

**No isolation; rely on test-author discipline (current state).** Rejected. Manual `try/finally` works only when tests succeed. Crashed tests leave orphans. Two of the existing test files already follow this pattern; codifying it as the design accepts the orphan-row risk indefinitely.

**DROP/CREATE DATABASE between every test.** Rejected. Two orders of magnitude slower than TRUNCATE CASCADE, with no correctness benefit.

### For D4 — CI strategy

**Self-hosted runner on lira.** Rejected. Couples CI uptime to a single dev machine. Adds runner-agent maintenance. Solves a problem the service container does not have.

**Mark DB tests, skip in CI.** Rejected. Codifies the silent-skip pattern the recon already found. Verifies almost nothing real about CORE in CI; CORE is database-shaped.

**Self-host Postgres alongside the GitHub runner separately from the job.** Rejected as overkill — exactly what the service container provides natively.

## References

- `.specs/state/2026-04-27-test-environment-recon.md` — recon baseline.
- ADR-015 — establishes the consequence-chain attribution shape; D2 added the `approval_authority` CHECK constraint that motivates the post-create-overlay question in D1.
- ADR-011 — workers own blackboard attribution; relevant because worker session ownership is what makes transactional rollback structurally impossible (D3 rationale).
- `src/shared/infrastructure/database/models/` — schema authority per D1.
- `tests/conftest.py` — target of restructure under D2/D3.
- `infra/sql/db_schema_live.sql` — retires under D1.
- `infra/scripts/reset_test_db.sh` — retires under D2.
- `tests/test_smoke_db.py` — smoke-test claim about `sql/001_consolidated_schema.sql` retires under D1.
- Follow-up (separate ADR): production-migration story. D1 forces this question without answering it. Production has 172 rows in `autonomous_proposals`, raw-SQL patches in `infra/scripts/migrations/` are partially applied, no Alembic baseline exists. The decision is between rebuild-from-models (data loss), Alembic with a baseline migration, or hand-written ALTER scripts indefinitely. Out of scope for ADR-016.
- Follow-up (Band D issue): `proposal_consequences` SQLAlchemy model. Prerequisite for D1 to produce a faithful schema.
- Follow-up (Band D issue): conftest restructure implementing D2/D3. Promotes `_prime_service_registry`, retires `_ensure_blackboard_table` and the existing manual `try/finally` cleanup boilerplate.
- Follow-up (Band D issue): CI workflow update implementing D4. Adds the Postgres service container to `ci.yml` and `core-ci.yml`.
