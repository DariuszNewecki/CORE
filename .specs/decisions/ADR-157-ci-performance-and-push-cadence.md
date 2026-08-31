---
kind: adr
id: ADR-157
title: ADR-157 — CI performance: complete the ADR-115 tier split, remove the duplicate Smoke gate, target the full gate on every push
status: proposed
---

<!-- path: .specs/decisions/ADR-157-ci-performance-and-push-cadence.md -->

# ADR-157 — CI performance: complete the ADR-115 tier split, remove the duplicate Smoke gate, target the full gate on every push

**Status:** Architecture approved (governor, 2026-08-31), conditional on the D3 implementation
checklist below. D1+D2 cleared to implement immediately. Revised three times after technical
counter-review ("BigBrother"); every claim across all three rounds was checked against the repository
before being accepted, corrected, or (once) rejected — see Context.
**Date:** 2026-08-31
**Prompted by:** an external review ("BigBrother") arguing that CORE's "push `main` once daily" habit
turns GitHub into a stale shared-memory surface for multi-agent collaboration, plus this session's own
measurement of the actual CI cost structure.
**Extends:** ADR-115 (CI ephemeral, hermetic infrastructure) — this ADR completes ADR-115 D4, which
was accepted 2026-06-19 and partially implemented, and refines one detail of D4's job-boundary design
(see D3).

---

## Context

### The external proposal

BigBrother's argument, verbatim in substance: an unpushed commit is invisible to other collaborators
(human or agent); a stale `main` risks duplicate or already-fixed work; branch protection is disabled
so commits already land on `main` before the ~25-minute workflow finishes, meaning "full-suite verified"
is not actually what `main` guarantees today. Its recommendation: push every coherent unit immediately,
have every agent report the exact SHA it started from, replace per-push CI with a fast gate
(governance checks, lint, relevant tests), and move the full DB-and-coverage suite to a nightly /
pre-release / post-high-risk-change cadence — trading permanent full-suite verification for
collaborative freshness.

### What this session measured, directly, before responding

- **Branch protection is off** (`GET /branches/main/protection` → 404, confirmed). Two of the last 20
  pushes to `main` had `CORE CI` **fail on a real blocking governance finding** (not a flake — a
  namespace-manifest registration gap), and both landed on `main` anyway, fixed by the next commit.
  BigBrother's premise is accurate: today's `main` is already only as good as its last human/agent
  follow-through, not as good as its last green CI run.
- **Two workflows both run the full test suite on every push**, and they disagree in kind:
  - `ci.yml` ("CI (Smoke)"): `poetry run pytest -q`, no service containers. With no reachable database,
    the ADR-115 D2 skip-guard fires and skips the DB-backed tests. `pytest -q` prints a skip count in
    its default summary, so this is not literally hidden from anyone who reads the log — but nothing
    gates on that count, and the job's green checkmark looks identical whether it ran everything or
    skipped a large fraction of the suite. 7–12 minutes per push for a result that is, at best, a
    strict subset of what `validate` (below) already produces in a stronger environment.
  - `core-ci.yml`'s `validate` job: real Postgres 17 + Qdrant service containers (ADR-115 D1), the full
    suite, coverage gate. This is CORE's one honest full-suite signal.
  `ci.yml` is strictly dominated by `validate` and has already diverged from it on a real push (Smoke
  green, `validate` red, same commit) — two contradictory "tests passed" signals for the same SHA.
- **Per-step timing on a clean `validate` run** (via the Actions API, not estimated): container init
  24s, `poetry install` 2s (cache hit), constitutional audit 138s, `ruff check` 1s, `pip-audit` 2s,
  vocabulary check 7s. **`pytest --cov=src ...` alone: 1273 seconds** — 21 of the ~25 total minutes,
  run as a single serial process over the complete suite (**4,071 test cases across 554 files**,
  verified via `pytest --collect-only`) with no parallelism.
- **Test markers are partially applied, not untouched.** `pyproject.toml` declares
  `unit`/`integration`/`e2e`/`slow`/`trio`. Verified against HEAD (`e51374b3`): **48 files marked
  `integration`** (via `pytestmark = [pytest.mark.integration]`), **0 marked `unit`**, and exactly
  **one file** (`tests/cli/test_offline_audit_regression_544.py`) carries both `@pytest.mark.e2e` and
  `@pytest.mark.slow` — decorator-style, on presumably a single test, unrelated to the module-level
  `pytestmark` convention used for `integration`. That file does **not** reference
  `session`/`AsyncSession`/`get_session`/`db_session` — it needs no database. Separately, a
  session/DB-reference heuristic (grep for those four terms) matches **135 files total**: 46 overlap
  the 48 already-`integration`-marked files, 89 are unmarked candidates, and 2 already-marked files
  fall outside the heuristic (they open a session through a path the grep doesn't catch). ADR-115 D4
  ("split CI into a unit job and an integration job using these markers," accepted 2026-06-19) is
  therefore **partially implemented on the test-marker side and not implemented at all on the workflow
  side** — `validate` still runs everything in one job, one process, regardless of marker.
- **Two `autouse=True` fixtures in `tests/conftest.py` run after every test, unconditionally, whenever
  the database happens to be reachable** — `_truncate_core_tables_between_tests` (a real
  `TRUNCATE CASCADE` + commit round-trip) and `_dispose_db_engines_after_each_test` (tears down the
  entire engine/connection-pool state). Neither checks whether the test that just ran actually touched
  the database. In the `validate` job the database is always reachable, so **all 4,071 test cases pay
  this cost today, including pure unit tests that never open a session.** The `TRUNCATE` fixture was
  independently flagged by BigBrother; the engine-disposal fixture was found separately this session by
  reading the same file. Neither was part of the original external proposal. This is a plausible major
  contributor to the 1273s independent of parallelism — see D3.
- **No `concurrency:` block exists in any workflow.** This repo's own git history from the last two
  days (the #842 series) shows multiple pushes within minutes of each other fixing the same issue —
  each one triggering a full, independent 25-minute ephemeral-DB run that gets superseded before it
  finishes. Pure waste, unrelated to any strategic question.
- **The repository is public, not a fork.** GitHub gives public repos unmetered free minutes on
  standard hosted runners — parallelization/sharding costs engineering time, not money, here.
- `daily_sync.yml` already runs the constitutional audit (not the full pytest/coverage suite) nightly
  at 08:00 UTC. There is currently no nightly full-suite-with-DB job.

### External research (2026, verified via web search, not assumed)

- **`pytest-xdist`** (`-n auto`) is the standard lever for a serial suite like this — reports of 4–8x
  wall-clock reduction on mixed suites are common. DB-backed tests must not share one Postgres
  connection/schema across workers; per-worker isolation (keyed on `PYTEST_XDIST_WORKER`) is the
  documented fix, and it is real engineering work given this project's async session fixtures — not a
  config flag. **Demoted to a conditional follow-up in D3** rather than a day-one requirement.
- **Job-level sharding** (matrix + `pytest-split` or equivalent) is a complement, not a substitute, if
  the plain two-job split isn't fast enough on its own; each shard re-pays container startup (currently
  ~24s), so shard count should stay low (3–4) if it's ever needed.
- **Selective/impacted-test execution** (`pytest-testmon` and similar) is documented as unreliable with
  subprocess calls, file-based fixtures, and non-code config changes — exactly this project's
  DB/fixture-dependent shape. Not adopted as a gating mechanism; at most a future local-dev convenience.
- **Self-hosted runners and third-party faster-runner services**: evaluated and not adopted for now —
  no current option offers a compelling win over `xdist` plus free public-repo minutes once D3 lands,
  and for a solo maintainer the ongoing maintenance cost of self-hosting isn't justified by a marginal
  gain. Worth revisiting only if container image pull/cold-start becomes the binding constraint after
  D3 — it currently isn't (container init measured at ~24s).
- **Concurrency cancellation** must be event-aware: a manual `workflow_dispatch` against a specific
  historical SHA (the `#827` use case already supported by these workflows) must not be auto-cancelled
  by an unrelated subsequent push — see D2. Separate note for later: if branch protection is ever
  added, a top-level `paths-ignore` leaves required status checks stuck "Pending" forever (a known
  GitHub limitation); any future path-based skipping must use a conditional step inside a job that
  always runs, not a workflow-level `paths-ignore`.
- **GitHub Merge Queue** does not apply — CORE has no PR-based workflow (direct-to-`main`), and current
  merge-queue tooling has known rough edges for this repo's shape. Not adopted regardless.

## D3.3 execution note (2026-08-31)

Implemented and measured directly, on the dev box against the real (LAN) test database — not just
argued from source reading. A full-suite local run was attempted first as a clean before/after
baseline; it had to be killed both before and after the fix (once for being too slow to be practical
over LAN latency even after ~30 minutes, once for a genuine stall on the wheel-install e2e test that
appears network-egress-dependent in this sandbox) — so no exact before/after wall-clock number came
out of this environment, and the authoritative timing measurement for D3.8 is deferred to the actual
CI run against localhost containers, which is the correct environment for that number anyway.

What *did* come out of local measurement, directly: the new fail-fast fixture
(`_fail_unmarked_tests_that_touch_db`) caught a real classification gap neither classification agent's
literal-grep heuristic could see — `tests/body/evaluators/test_constitutional_evaluator.py` calls a
real `ConstitutionalEvaluator.execute()`, which reaches `KnowledgeService.get_graph()` →
`get_session()` several call-layers below the test file itself, with no `session`/`AsyncSession`/
`get_session`/`db_session` literal anywhere in the test file. 14 of its 30 tests (exactly those whose
effective `validation_scope` includes `constitutional_compliance`, by inspection) needed
`@pytest.mark.integration`; the other 16 explicitly scope to `pattern_compliance`/
`governance_boundaries` only and never touch the database. A targeted sweep for the same pattern
(`ConstitutionalEvaluator(` and `load_knowledge_graph`/`AuditorContext(` elsewhere in `tests/`) found
no further instances — all other candidates were already correctly mocked. This is exactly the
failure mode the fail-fast fixture exists to catch, and it caught one on its first real run.

## D3 implementation checklist (approved with conditions, 2026-08-31 — third review round)

Verified before acceptance: `test_offline_audit_regression_544.py` looks for
`dist/core_runtime-*.whl` and calls `pytest.skip("No core_runtime-*.whl in dist/. Run poetry build
first...")` if none exists; `dist/` is gitignored and `core-ci.yml` never runs `poetry build`. The
actual log from the last full run confirms this precisely: `4061 passed, 1 skipped ... in 1269.08s` —
the single skip on the entire 4,071-test suite is this test. Routing it into a DB-less `not
integration` job (D3.2/D3.4) does not make it run; it just relocates the same skip. Three corrections
fold into D3, no new ADR round needed:

- **Build the wheel before the no-DB test job runs** (`poetry build` as a step ahead of pytest in that
  job), so the job actually executes this test instead of relocating its skip. Rename that job
  `hermetic` rather than `unit` in the resulting workflow — it contains a real e2e test, "unit" would
  be inaccurate.
- **Coverage must not leak into the D3.4 collect-only ratchet.** `pyproject.toml`'s global `addopts`
  already includes `--cov=src` and two report flags — any bare `pytest --collect-only` invocation
  (including the disjoint/union ratchet) inherits them and can create or overwrite coverage data as a
  side effect. The ratchet's collection commands must pass `--no-cov` (or otherwise neutralize the
  global `addopts`) explicitly; coverage ownership belongs solely to the two real test-execution
  commands (D3.7).
- **The combine job must produce `coverage.xml` and keep the existing Codecov upload
  (`fail_ci_if_error: true`)** — `coverage combine` + `coverage report --fail-under=38` alone drops the
  `coverage xml` step the current single-job `validate` already has wired to Codecov. Add `coverage
  xml` after the combine, before the upload, in the same job.
- **The `CORE_UNIT_JOB` fail-not-skip fix (D3.4) only protects the future `hermetic`/unit job.** It does
  nothing for D3.3's interim measurement step, which runs the *existing* single-job suite with the DB
  reachable, specifically to isolate the fixture-fix's effect before the split exists. During that
  interim run, an unmarked test that opens a DB session should also fail immediately rather than pass
  silently un-isolated — add the same fail-fast behavior (or an equivalent explicit assertion) to that
  measurement step, not only to the later job split.

## Decision

### D1 — Delete `ci.yml` ("CI (Smoke)")

It is strictly dominated by `core-ci.yml`'s test job: same tests, weaker (DB-less) environment, no
coverage gate, no lint, no audit, and it has already produced a result that diverged from the honest
job on a real push. Its only historical value (fast feedback without waiting on containers) is
superseded by D3, which makes the real job fast instead of running a weaker one in parallel.

### D2 — Add event-aware `concurrency` cancellation to every remaining workflow

`concurrency: { group: "${{ github.workflow }}-${{ github.event_name == 'workflow_dispatch' &&
github.run_id || github.ref }}", cancel-in-progress: true }` on `core-ci.yml`, `docs.yml`, and
`daily_sync.yml`. Push/PR runs on the same ref still dedupe and cancel each other (the actual waste
observed in this repo's recent history); a `workflow_dispatch` run gets a unique group per invocation
(via `run_id`) so an intentional dispatch against an old SHA is never cancelled by an unrelated later
push. Exact grouping expression to be sanity-checked against GitHub's current expression syntax at
implementation time, not assumed correct from this draft.

### D3 — Complete ADR-115 D4, in a dependency-correct, risk-ordered sequence, measuring before escalating

Sequence (each step's dependency on the previous is deliberate — D3.2 cannot run before D3.1 corrects
the marker set, or still-unmarked DB tests silently lose isolation during the measurement window):

1. **Extract a `static-checks` job** from `validate`: vocabulary freshness check, the constitutional
   audit (`--offline`), `ruff check`, `pip-audit`. None of these need the database in principle;
   confirm the vocabulary check specifically has no hidden DB dependency before moving it, rather than
   assuming. This alone removes ~150s from the critical path of whatever job still runs tests, and
   makes these checks report independently instead of being buried as steps inside a job named for
   something else.
2. **Correct and complete the marker classification, first.** Review the 48 already-`integration`-marked
   files for correctness (don't assume the prior marking is right, including the 2 that fall outside
   the DB-reference heuristic — confirm why). Review the 89 unmarked heuristic candidates and mark each
   `integration` only if it genuinely opens a live session (a file can reference `AsyncSession` in a
   type hint or a mock without needing one). `tests/cli/test_offline_audit_regression_544.py`
   (`e2e`+`slow`) is confirmed DB-free this session — it needs no `integration` marker and belongs in
   the `unit` job; its `slow` tag means its actual runtime should be watched in D3.8's measurement, not
   that it needs a third job. Everything else unmarked is implicitly `unit` — no marker required. The
   real partition boundary is binary (`integration` / `not integration`); `e2e` and `slow` are
   orthogonal descriptive tags, not a third bucket, once this file's placement is settled.
3. **Only then fix the two `autouse=True` fixtures** in `tests/conftest.py`
   (`_truncate_core_tables_between_tests`, `_dispose_db_engines_after_each_test`) to run only when the
   test that just executed is marked `integration` (e.g. `request.node.get_closest_marker
   ("integration")`), not merely "whenever the DB happens to be reachable." **Measure the effect on the
   existing single-job suite before touching job topology at all** — this isolates the fixture-overhead
   variable from the job-split variable, so D3.4 is evaluated against a clean baseline instead of two
   unmeasured changes conflated together.
4. **Split into an exhaustive, complementary partition:** a `unit` job (`-m "not integration"`, no
   service containers) and an `integration` job (`-m integration`, keeps the Postgres 17 + Qdrant
   service containers from ADR-115 D1). `-m X` and `-m "not X"` are complementary and exhaustive over
   the full collection by construction — the first draft's flaw was adding extra exclusion clauses
   (`and not e2e and not slow`) that broke that property; D3.2 removes the need for them. This is a
   deliberate refinement of ADR-115 D4's original phrasing ("the integration job runs the full suite
   including integration tests") — running the unit tests a second time inside the DB-backed job would
   be correct but wasteful; a complementary partition plus combined coverage (D3.7) reaches the same
   "coverage measured against the complete suite" outcome without re-executing anything twice.
   **Two executable ratchets, added as CI steps, not left as a one-time manual check:**
   - A verification step collects node IDs under each job's `-m` selector (`pytest --collect-only -q`)
     and asserts the two sets are disjoint and their union equals the full collection. Mathematically
     guaranteed for a clean `X`/`not X` split, but this catches real-world drift the math doesn't cover
     — a file silently failing to collect in one job's environment (import error, missing fixture
     dependency), a typo'd marker name slipping past `--strict-markers` in some future refactor, or a
     `-k` filter accidentally layered on top of `-m` later.
   - In the `unit` job specifically, a DB-session attempt must **fail**, not silently invoke the
     existing `_skip_db_tests_when_unreachable` guard (which is correct behavior for a contributor
     without local Postgres, but wrong here — a forgotten `integration` marker would otherwise show up
     as a green skip, not a red flag). Concretely: an env var (e.g. `CORE_UNIT_JOB=1`), set only in the
     `unit` job, switches that fixture's unreachable-DB branch from `pytest.skip(...)` to
     `pytest.fail(...)`.
5. **`unit` job runs under `pytest-xdist -n auto`** immediately — no DB contention risk here, this is
   the safe, standard win.
6. **`integration` job runs serially at first** — no `xdist`, no per-worker database isolation, on
   initial landing. Per-worker isolation is real engineering risk and is not justified until it's known
   the plain split isn't enough.
7. **Coverage artifact contract, spelled out explicitly** (the two jobs run on separate, ephemeral
   runners with no shared filesystem): both `unit` and `integration` run `coverage run` (or `pytest
   --cov` with `COVERAGE_FILE` set to a job-unique path, e.g. `.coverage.unit` / `.coverage.integration`)
   and upload that data file as a uniquely-named artifact (`actions/upload-artifact`, e.g.
   `coverage-unit-data` / `coverage-integration-data`). A final `coverage-combine` job
   (`needs: [unit, integration]`) checks out the **same commit SHA** both test jobs ran against,
   downloads both artifacts (`actions/download-artifact`), runs `coverage combine` over both data
   files, then `coverage report --fail-under=38`. Without this explicit transfer step the combine job
   has nothing to combine — noted here so implementation doesn't skip it as "obvious" and discover the
   gap at review time.
8. **Measure real timings** for `static-checks`, `unit`, and `integration` once 1–7 are live and
   compare against the 1273s/25min baseline recorded in this ADR. Only then decide whether
   `xdist`-with-per-worker-isolation on `integration`, or matrix sharding, is worth its complexity —
   against a measured number, not a projection.

### D4 — Target the full gate on every push and PR; treat nightly-only tiering as a fallback, not a moral failure, if D3.8's measurement doesn't get there

Once D3 lands, the goal is that the full, honest gate (static checks, unit, integration, combined
coverage) is fast enough that there is no forced tradeoff between "main reflects the latest work" and
"main is fully verified." This is a **feasibility bet, evaluated at D3.8's measurement** — not a claim
that any tiered alternative is dishonest. A *clearly labeled* partial push-gate plus a nightly full gate
is a legitimate, transparent design, not equivalent to the *silent* skip-guard degradation ADR-115
rejected. If D3.8 shows the complete gate genuinely can't land in a reasonable window even after D3's
fixes, a labeled nightly tier is the correct next conversation, not a fallback to be avoided at all
costs. `daily_sync.yml`'s existing audit-only nightly cron is unchanged either way, and remains valid as
an independent safety net regardless of how D4 resolves.

### D5 — Reject self-hosted runners and impacted-test-selection as gating mechanisms, for now

No live self-hosted or third-party runner option offers a compelling win over `xdist` + free
public-repo minutes once D3 is in place; for a solo maintainer the ongoing maintenance burden isn't
justified by a marginal gain. Selective execution (`pytest-testmon` etc.): documented false-negative
risk on DB/fixture-dependent tests makes it unsafe as a required check; not adopted here. Both may be
reconsidered later against concrete evidence, not speculative future need.

### D6 — Push-cadence and SHA-handoff discipline takes effect after D2, not after D3

BigBrother's points on pushing every coherent unit immediately and every agent starting by fetching
`origin/main` and reporting the exact SHA are sound, are not workflow YAML (recorded as an operating
norm in CLAUDE.md / session memory, not implemented in this ADR), and **should take effect as soon as
D2 (concurrency cancellation) lands — not gated on D3's full completion.** Delaying this until D3.8's
measurement would preserve the stale-shared-memory problem this ADR exists to help solve, for no
benefit: D2 alone already removes the actual waste (superseded runs completing anyway) that motivated
the old "batch push once per session" guidance. The existing memory
"batch push once per session, CI runs 20-25min regardless of change size" should be revised once D2 is
live, ahead of D3's speed work — the remaining ~25-minute wait per push is a tolerable, temporary cost
of fixing the collaboration-visibility problem, not a reason to keep batching.

## Consequences

- `ci.yml` is removed. `core-ci.yml` gains a `static-checks` job, a `unit` job, an `integration` job, a
  `coverage-combine` job, and event-aware `concurrency` blocks across workflows.
- The `_truncate_core_tables_between_tests` / `_dispose_db_engines_after_each_test` fix (D3.3) is
  measured in isolation before any job-topology change, so its contribution to the 1273s baseline is
  known rather than conflated with the partition-and-parallelize changes — and it only runs safely once
  D3.2 has corrected which tests are actually `integration`.
- Coverage honesty now depends on the artifact-transfer + combine step (D3.7) rather than a single job
  reading the complete suite — a real new failure mode to guard in review (a partition that isn't
  actually exhaustive, or a missing artifact upload, would silently under-report coverage without
  necessarily failing loudly), mitigated by the two ratchets in D3.4.
- Per-worker DB isolation and/or matrix sharding remain explicitly deferred, conditional follow-ups
  (D3.6, D3.8) — not committed to by this ADR.
- No change to ADR-115 D1 (ephemeral, hermetic infrastructure). D3 refines D4's job-boundary detail
  (complementary partition + combine instead of "integration job runs everything") while preserving
  D4's intent and D5's coverage-honesty requirement.
- Session memory `feedback_batch_push_once_per_session` is revised once D2 is implemented — ahead of,
  not after, D3 — per D6.

## Alternatives considered

- **BigBrother's tiered model as originally proposed** (fast gate on push, full suite nightly only).
  Not adopted as the primary strategy for now — see D4 — but explicitly held as the correct fallback,
  not rejected outright, if D3.8's real measurement shows the full gate can't be made fast enough.
- **Keep both `ci.yml` and `core-ci.yml`.** Rejected — status quo, ~10 minutes of duplicated compute
  per push with a documented case of the two disagreeing.
- **Integration job re-runs the complete suite (unit + integration) under DB services**, per ADR-115
  D4's original literal phrasing. Superseded by the complementary-partition-plus-combine design in
  D3.4: same coverage honesty, without re-executing the unit tests a second time.
- **A third job for `e2e`/`slow`-marked tests.** Rejected once the one existing file was checked and
  found DB-free — the real partition need is binary (`integration`/`not integration`); a third bucket
  would have been solving an imagined problem, not the observed one.
- **Self-hosted runner pointed at a persistent, hand-maintained test DB.** Not seriously considered —
  this is the exact LAN-dependency architecture ADR-115 D1 already reasoned through and replaced.
  Only "self-hosted hardware, still-ephemeral containers" was in scope for D5's evaluation, and even
  that was rejected for now on cost/benefit, not on hermeticity grounds.
- **`pytest-testmon` / impacted-test selection as the push-time gate.** Rejected — see D5; false-negative
  risk on this suite's DB/fixture-dependent tests is a correctness problem, not a speed one.
- **Mandate `xdist` + per-worker DB isolation immediately, in the same change as the job split.**
  Rejected — conflates the riskiest, least-proven piece of engineering with the safest, best-understood
  one (the partition itself), and forecloses learning whether the simpler fix (D3.3's fixture
  correction) already solves most of the problem.
- **Fix the `autouse` fixtures before correcting the marker set.** Rejected — restricting truncation/
  disposal to `integration`-marked tests before the marker set is corrected would strip isolation from
  still-unmarked DB tests during the very measurement meant to establish a clean baseline.
- **Delay the push-cadence policy change until D3 is fully measured.** Rejected — see D6; it would
  preserve the stale-shared-memory problem for no reason, since D2 alone removes the waste that
  motivated the old batching guidance.

## References

- ADR-115 — CI ephemeral, hermetic infrastructure; D1 (services containers, unchanged), D4 (tier
  split, accepted, partially implemented on the marker side, completed on the workflow side by this
  ADR; job-boundary detail refined by D3.4), D5 (coverage gate must reflect the complete suite —
  preserved via the combine step, D3.7).
- `.github/workflows/ci.yml` — removed by D1.
- `.github/workflows/core-ci.yml` — restructured by D2/D3.
- `.github/workflows/daily_sync.yml` — unchanged; referenced by D4 as the existing nightly safety net.
- `tests/conftest.py` — `_truncate_core_tables_between_tests`, `_dispose_db_engines_after_each_test`
  (fixed by D3.3), `_skip_db_tests_when_unreachable` and `_require_db_infrastructure_in_release_mode`
  (ADR-016 D3 / #773 T5.1 — unchanged by this ADR, but its skip branch gains the `CORE_UNIT_JOB`
  fail-instead-of-skip behavior per D3.4).
- `pyproject.toml` — `[tool.pytest.ini_options]` `markers`, made real and complete by D3.2.
- #842 — the recent commit series whose rapid-fire pushes motivated D2's measurement.
