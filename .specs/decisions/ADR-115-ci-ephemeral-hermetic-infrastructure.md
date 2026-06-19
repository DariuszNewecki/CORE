---
kind: adr
id: ADR-115
title: ADR-115 — CI runs against ephemeral, hermetic infrastructure seeded from canonical schema
status: accepted
---

<!-- path: .specs/decisions/ADR-115-ci-ephemeral-hermetic-infrastructure.md -->

# ADR-115 — CI runs against ephemeral, hermetic infrastructure seeded from canonical schema

**Status:** Accepted — governor-delegated 2026-06-19 (the governor entrusted the technical CI-posture decision to the implementer; this ADR records the design and reasoning for review).
**Date:** 2026-06-19
**Grounding:** the CORE honesty thesis (a gate must measure what it claims to measure); schema-as-truth (`infra/sql/db_schema_live.sql` is canonical, no migration framework, per the existing DB posture); reproducibility (a build's result must not depend on machine- or network-specific state).
**Prompted by:** the smoke-suite remediation of 2026-06-19 (#681) — the suite was red because CI could not reach the LAN test database named in `.env.test`; closing that surfaced that the deeper failure is an *architectural* one, not a test bug.

---

## Context

CORE's test suite is split, in practice, into three kinds of check that the CI configuration
currently conflates:

- **Static checks** — lint, vocabulary-projection freshness, README count drift. Hermetic; no
  external state.
- **Unit tests** — hermetic; no external state.
- **Integration tests** — require a real PostgreSQL (and, for some paths, Qdrant). ~85 tests.

All three run under one `pytest` invocation that loads `.env.test`, which points
`DATABASE_URL` at `postgresql+asyncpg://…@192.168.20.23:5432/core_test` and `QDRANT_URL` at
`http://192.168.20.22:6333` — **hosts on a private LAN that a GitHub-hosted runner cannot
route to.** This single coupling is the root cause of a cluster of symptoms:

1. **The smoke job hung ~50 minutes** (#681): integration tests blocked on asyncpg connect
   attempts to an unreachable host, with no per-test timeout, until the job was killed.
2. **`Validate` cannot pass.** Its `pytest --cov-fail-under=45` step, measured with the
   integration tests skipped (forced locally, 2026-06-19), yields **TOTAL coverage 38.0%** —
   the ~85 DB-backed tests are worth ~7 coverage points. The gate fails by ~7 points not
   because coverage regressed but because the tests that produce it never run in CI.
3. **`Validate`'s lint step needs a server.** `core-admin check lint` is a thin client over a
   core-api server at `127.0.0.1:8000` that does not run in the CI job — so even with coverage
   solved, the step fails.
4. **The `core_test` database drifts.** Because CI never builds the DB, the LAN `core_test`
   instance is maintained by hand and drifts from the canonical schema (`column does not exist`
   failures have recurred); it can only be rebuilt server-side.

The interim fix (#681) added a conftest guard that **skips** DB-backed tests when the database
host is unreachable. That made smoke green and stopped the hang — correct as a stop-gap — but
it is the wrong steady state for CI: a green build that silently skipped ~85 integration tests
and dropped coverage to 38% is a gate measuring less than it claims. The honest resolution is
not to skip the tests; it is to **give CI the infrastructure to run them.**

Mature CI never depends on a network host maintained by hand. It provisions its own
throwaway infrastructure on every run, seeded deterministically from a canonical source.

## Decision

### D1 — CI provisions ephemeral PostgreSQL and Qdrant per run, seeded from canonical schema

The integration test job declares PostgreSQL and Qdrant as ephemeral service containers,
spun up fresh per job. The database is seeded from `infra/sql/db_schema_live.sql` — the
canonical schema-as-truth — via `psql -f`, the same mechanism used server-side. `DATABASE_URL`
and `QDRANT_URL` are pointed at `localhost`. The integration suite then **runs** against real,
disposable infrastructure: hermetic, reproducible, and free of any LAN dependency.

**Endpoint resolution.** `shared.config` loads `.env.test` with `override=True` under pytest,
and the committed `.env.test` hardcodes the LAN host — so setting `DATABASE_URL` as a job env
var is insufficient (the dotenv load wins). The integration job therefore rewrites the *runner's*
`.env.test` endpoints to `localhost` (a contained `sed` over the ephemeral checkout) before
running tests. The committed `.env.test` is unchanged: it remains the local-dev pointer to the
LAN test DB. The integration tests self-create and clean their own rows, so seeding the schema
(`db_schema_live.sql`, DDL for ~249 tables) is sufficient — no data fixtures are required.

This is the load-bearing decision. D2–D5 follow from it.

### D2 — The DB-reachability skip-guard is reclassified as a local-dev convenience, not CI behavior

The conftest guard shipped in #681 (skip DB-backed tests when the DB host is unreachable)
remains in the tree, but its purpose is restated: it exists so a contributor **without** a
local PostgreSQL can still run the unit subset. In CI, the database is always reachable (D1),
so the guard never fires and **CI skips nothing.** The guard is a fallback for humans, not the
posture of the build.

### D3 — Lint runs statically in CI, not through the API server

CI lints by invoking the static linter directly (`ruff check src tests`) rather than
`core-admin check lint`, which round-trips to a running core-api server. Linting is static
analysis; coupling it to a live HTTP service in CI is an architectural mismatch. The
server-backed `check lint` remains valid as the **interactive operator surface** (it is how a
human asks the running system to lint itself); CI simply uses the in-process path. The two are
different surfaces with the same underlying tool, not duplication.

Scope note (from implementation recon): the server-side lint route nominally runs `black
--check` *and* `ruff check` over `src/` + `tests/`. `black` is **stale** here — the codebase is
formatted with `ruff format` (the pre-commit hook), and `black 26.x` reports ~896 files would
reformat. CI therefore runs `ruff check` only; **format enforcement stays at the pre-commit
boundary**, where it already lives. A separate drift was surfaced and *not* fixed here: a few
test files fail `ruff format --check` under poetry's pinned ruff, indicating ruff-version skew
between pre-commit and the locked toolchain — recorded as follow-up, out of scope for the CI
infrastructure change.

### D4 — Tests are tiered with real markers; CI splits into a unit job and an integration job

The `unit` / `integration` markers already declared in `pyproject.toml` are **applied to 0 of
289 test files**. They are made real: every test that opens a database session (directly or via
fixture) is marked `integration`; the remainder are `unit`. CI then runs:

- a **unit job** — no service containers, `-m "not integration"`, fast, on every push/PR;
- an **integration job** — service containers (D1), the full suite including `integration`.

The coverage gate (`--cov-fail-under`) lives on the **integration job**, where the suite is
complete and the percentage is honest. Splitting the tiers also gives fast feedback on the
common path without waiting on container startup.

### D5 — The coverage threshold is retained, not lowered

`--cov-fail-under=45` stays. The 38% figure is an artifact of running an incomplete suite, not
a true coverage level; once D1 lets the integration tests run, the threshold is measured
against the whole suite and is met. Lowering the gate to accommodate skipped tests is
explicitly rejected (see Alternatives) — it would weaken a real gate to paper over a
provisioning gap.

## Consequences

- **The LAN dependency is removed.** CI no longer depends on `192.168.20.23` / `192.168.20.22`
  being reachable or correctly maintained. Builds become reproducible from the repository alone.
- **`core_test` drift ends as a class of problem** — for CI. Each integration run builds the DB
  fresh from `infra/sql/db_schema_live.sql`, so schema drift cannot accumulate in the path that
  gates merges. (The hand-maintained LAN instance used for local dev is a separate concern,
  unchanged here.)
- **The gates measure what they claim.** `Validate`/integration runs the integration tests and
  the 45% coverage gate is honest; the unit job gives fast, hermetic feedback.
- **CI gains its first `services:` blocks** and a schema-seed step — new machinery (~30–40 lines
  of workflow YAML plus a seed command). Integration-job wall-clock rises by container startup
  + seed time; the unit job stays fast and carries the common path.
- **The #681 guard keeps earning its place** as a local-dev affordance, now with a recorded
  reason rather than as an implicit CI crutch.
- **No production code changes** are required by D1/D2/D5; D3 touches CI invocation only; D4 is
  test-marker annotation plus the workflow split.

## Alternatives considered

- **Lower `--cov-fail-under` to ~35%.** Rejected — it weakens a real gate to match an
  artificially incomplete run. The coverage is not actually 38%; the suite is incomplete.
- **Give lint a server-less path and stop there.** Rejected as a complete answer — it fixes one
  of three symptoms (D3) while leaving the LAN coupling, the skipped integration tests, and the
  drift untouched. It is correct *as part of* D3, not as a substitute for D1.
- **Keep skipping integration tests in CI (the #681 stop-gap as steady state).** Rejected — a
  green build that silently skips ~85 tests and reports 38% coverage is a gate measuring less
  than it claims; it inverts the honesty thesis at the CI level.
- **Point CI at the LAN database (add the host/secret).** Rejected — it entrenches the original
  sin: CI depending on a hand-maintained network host. It would also still drift and still be
  unreachable from forks/external runners.
- **Do nothing; accept `Validate` red.** Rejected — `Validate` then provides no signal, and the
  reasons it is red are not visible without this analysis. (`Validate` was already red before
  the 2026-06-19 work; this ADR is what makes the path to green explicit.)

## References

- `.github/workflows/ci.yml` — the smoke (`CI (Smoke)`) job; becomes/feeds the **unit** job (D4).
- `.github/workflows/core-ci.yml` — the `Validate` job (vocabulary check, lint, coverage) and
  PR-linter; gains service containers + seed step (D1), static lint (D3), tier split (D4).
- `infra/sql/db_schema_live.sql` — canonical schema seeded into the ephemeral DB (D1).
- `tests/conftest.py` — the DB-reachability skip-guard (#681), reclassified by D2.
- `pyproject.toml` — `markers` (`unit` / `integration`, applied to 0 files today) made real by D4;
  `ruff` dependency used by the static lint path (D3).
- #681 — smoke-test drift fix and the skip-guard that prompted this ADR.
- Existing DB posture: schema-as-truth, no migration framework; `core_test` is a separate,
  drift-prone test DB rebuilt server-side.
