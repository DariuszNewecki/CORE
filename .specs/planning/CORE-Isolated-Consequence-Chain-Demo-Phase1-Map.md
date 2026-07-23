---
kind: planning
title: CORE — Isolated Consequence-Chain Demo — Phase 1 File/Change Map & Test Plan
status: draft
---

<!-- path: .specs/planning/CORE-Isolated-Consequence-Chain-Demo-Phase1-Map.md -->

# Phase 1 — Isolation-Substrate File/Change Map & Test Plan

**Companion to:** `CORE-Isolated-Consequence-Chain-Demo.md` (governing spec) and
`../decisions/ADR-155-isolated-consequence-chain-demo.md` (governing ADR).
**Baseline:** `f7430b25`, isolated clone `CORE-demo-consequence-chain`, branch
`feat/isolated-consequence-chain-demo`.
**Status:** Proposed change map only — **no production code implemented.** ADR-155 is
**accepted** (2026-07-23), subject to the design-decision resolutions below. **Implementation
of this map — including Phase 1 — remains blocked until the production-readiness soak closes
on 2026-07-26 09:17:45 CEST and the governor records the final verdict**; isolation from the
invoking repo does not exempt Phase 1 from that gate. Phase 1 is the isolation substrate:
clone create/cleanup, run identity + marker validation, disposable Compose, child-process
re-rooting, invoking-repo before/after fingerprint. **It adds no audit, sensor, proposal,
execution, or evidence scenario** (those are Phase 2) and **no CLI command surface** (Phase 3).

Every target below was verified to exist (or correctly not exist) in the clone at `f7430b25`
before being listed — this map is grounded in the actual tree, not assumed.

## Scope boundary

| In Phase 1 | Deferred |
|---|---|
| Validated local-clone creation, remote removal, marker-checked clone cleanup | The genuine chain scenario (Phase 2) |
| `run_id` generation + marker file + D3 cleanup validation | `get_proposal_chain()` API client method (Phase 2) |
| Disposable `infra/demo/compose.yaml` + a compose driver | `demo` CLI namespace / `consequence-chain` command (Phase 3) |
| Child-process re-rooting primitive (inherited stdio, explicit env) | `scripts/demo.sh` wrapper, `install-core.sh` change, docs (Phase 3) |
| Invoking-repo before/after fingerprint | The D10 15-assertion model beyond isolation assertions (Phase 2) |

## File/change map

Layer discipline (surfaced for ADR review): **primitives live in `src/shared/` (reusable,
governed sanctuaries); substrate orchestration + typed records live in `src/cli/logic/demo/`.**
The spec §4 places orchestration under `cli/logic/demo` and primitives under `shared/*`; this
map keeps that split. The spec permits path changes "if existing module conventions demand it"
but not boundary changes.

| # | Path | New/Edit | Phase-1 responsibility | Grounding at `f7430b25` |
|---|---|---|---|---|
| 1 | `src/shared/config.py` | Edit | Add `CORE_DEMO_STATE_DIR` to `Settings` (class at L93), defaulting to the platform per-user local-state dir **outside** the invoking repo; never shell-expanded (D3). | `class Settings(BaseSettings)` present L93. |
| 2 | `src/shared/utils/subprocess_utils.py` | Edit | Add a narrow child-process primitive: inherited stdio, **explicit** `env` (no inheritance of live `.env`), explicit cwd, no shell (D5); add fixed `docker compose` command builders (up/down/ps/logs) taking a project name + compose-file path. Reuses the existing sanctuary, no new shell site. | Sanctuary present: `run_command_async` L38, `run_poetry_command` L64, `run_systemctl` L135. |
| 3 | `src/shared/infrastructure/git_service.py` | Edit | Add to `GitService` (class L54): `create_disposable_clone(head_sha, dest)` using **copied objects, `--no-hardlinks`, remote removed** (D2); `clone_has_no_remote()` assertion; `marker_checked_remove(path, run_id)` implementing the D3 escape/marker/parent/root guards. Reuses existing Git sanctuary. | `commit_paths` L248, `create_worktree` L382 present; **no clone/cleanup helpers yet** — additions, not overlaps. |
| 4 | `src/cli/logic/demo/__init__.py` | New | Package marker for the demo substrate logic. | `src/cli/logic/` is the established command-support-logic area; `demo/` absent. |
| 5 | `src/cli/logic/demo/models.py` | New | Typed `RunIdentity` (opaque UUID `run_id`, state-dir root, marker path), `IsolationFingerprint` (invoking-repo HEAD, index tree, tracked-tree hash, sorted pre-existing untracked paths+hashes), and a `PhaseResult`/assertion record shell. **Phase 1 populates only the run-identity and fingerprint records**; assertion/evidence records are stubbed for Phase 2. | New; spec §4 row. |
| 6 | `src/cli/logic/demo/isolation.py` | New | Substrate orchestration (no scenario): (a) generate `run_id` + write marker; (b) call `GitService.create_disposable_clone`; (c) prove clone isolation (no remote, seed-path checks deferred to Phase 2, `.intent/` hash captured); (d) fingerprint the invoking repo before/after; (e) bring up/tear down the disposable Compose project via the D5 primitives; (f) marker-checked cleanup. Delegates all process/git/fs to the sanctuaries above — **no direct `subprocess`/`shutil`/`Path.write_*`.** | New; the "child-process re-rooting" + "before/after fingerprint" homes. |
| 7 | `infra/demo/compose.yaml` | New | Ephemeral PostgreSQL + Qdrant only (D4): no fixed `container_name`, loopback-only, dynamic host ports, tmpfs storage, schema referenced from the canonical root `schema.sql` via the same bootstrap mechanism `install-core.sh` uses — not copied into the demo, not read from the invoking checkout at execution time (ADR-155 design decision 3) — health checks, `restart: "no"`, `core.demo.run_id` labels. Project name supplied at runtime from `run_id`. | `infra/demo/` absent — created here. |

**Not touched in Phase 1 (explicitly):** `src/cli/resources/demo/*`, `src/cli/logic/demo/
consequence_chain.py`, `src/api/cli/proposals_client.py` (`get_proposal_chain`), `scripts/
demo.sh`, `install-core.sh`, `README.md`/`docs/*`, and **anything under `.intent/`** (read-only;
ADR-155 grants no `.intent/` write).

## Constitutional compliance checklist (Phase 1)

- All in-clone filesystem writes route through `FileHandler` or `GitService` (no bare
  `Path.write_*`) — `governance.mutation_surface.filehandler_required`.
- All process spawns route through the `subprocess_utils` sanctuary — `governance.
  dangerous_execution_primitives`; the child-process primitive is the one sanctioned new site.
- No `src/shared/` import of `mind`/`body`/`will` — the substrate stays in shared + cli/logic.
- Every new public `def`/`class` carries a fresh `# ID:` UUID.
- No `.intent/` write anywhere; the substrate only *reads* and *hashes* `.intent/`.
- No `get_session`/`Settings` import outside sanctioned sites; the disposable `.env` and ports
  are passed as explicit config, never read from the live environment.

## Phase 1 test plan (subset of spec §6 that the substrate can satisfy without the chain)

Tests live under `tests/cli/logic/demo/` and `tests/shared/infrastructure/` (mirroring source).
Phase 1 proves isolation and cleanup **without** running any audit/mutation scenario.

| Spec ID | Phase-1 coverage | Test intent |
|---|---|---|
| U04 | Full | No `git reset --hard`/`git clean`/checkout-of-invoking-repo string anywhere in demo code (static assertion over the new modules). |
| U05 | Full | Clone uses copied objects (distinct inode / link-count 1 vs source), has **no** remote, is pinned to the captured `HEAD`. |
| U06 | Full | Cleanup guard refuses: wrong parent, missing marker, marker mismatch, symlink escape, root/`/` target, and the source-repo path — each a separate case. **Highest-value Phase-1 test.** |
| U07 | Partial | Compose project name, labels, and workspace paths all carry the same `run_id` (compose brought up/down; no scenario). |
| U13 | Partial | `.intent/` hash captured at clone time; a deliberately mutated clone `.intent/` is detected (source `.intent/` immutability is asserted by the fingerprint). |
| U15 | Partial | Every substrate wait (clone, compose health, teardown) has a deadline and names the phase that exceeded it. |
| E02 | Full | **Dirty invoking repo**: seed pre-existing staged, unstaged, and untracked files in a throwaway fixture repo; run the full substrate (clone → compose up → compose down → cleanup); assert HEAD, index tree, tracked bytes, and every pre-existing untracked byte are identical before/after. |
| E03 | Partial | Populate sentinel `DATABASE_URL`/`QDRANT_URL` in the parent env; assert the child process receives only generated run-specific endpoints, never the sentinels. |
| E04 | Full | Two concurrent substrate runs get distinct `run_id`s, ports, paths, Compose projects, and markers; neither's cleanup touches the other. |
| E06 | Full | Inject a failure immediately after clone: infra never started, invoking repo unchanged, clone removed (or retained-with-path per option). |
| E07 | Full | Inject a failure after Compose up: only the `run_id`-labeled Compose resources are removed; no other project touched. |
| E12 | Partial | SIGINT during compose-up and during teardown yields exit `130` and bounded cleanup (no scenario phases yet). |

**Deferred to Phase 2+** (need the real chain): U01–U03, U08–U12, U14; E01, E05, E08–E11,
E13–E15; all §6.3 negative-claim tests about findings/proposals/consequences. Phase 1's job is
to make the *ground* trustworthy so those later assertions mean something.

## Fixture strategy

- **Throwaway source repos**, not the clone-of-CORE, for U/E isolation tests — a tiny
  `git init` fixture with seeded dirty state keeps E02/E06 fast and lets us assert byte-equality
  without a 49 MB `.git`. The real clone-of-CORE path is exercised once in an integration test.
- **Real Docker Compose** for U07/E04/E07/E12 (the substrate's whole point is real disposable
  infra) — gated behind a `docker`-available marker so unit CI without Docker still runs U04/U05/
  U06. This mirrors the spec's D4/§6 intent; per prior project guidance, isolation/cleanup tests
  must use a real substrate, not mocked results, or they hide the multi-step failure modes.
- No live CORE DB/Qdrant/API/daemon, no live `.env` — every endpoint is generated per run.

## Design decisions (ADR-155 governor review, 2026-07-23)

The three placements this map originally left open are resolved by the governor's ADR-155
review (see ADR-155 "Governor review and design-point resolutions"). Recorded here for
implementers, not re-opened:

1. **Substrate home:** primitives extend `GitService` and `subprocess_utils` (this map's
   original choice, confirmed). No `shared/infrastructure/demo/` module.
2. **Compose driver placement:** raw `docker compose` command builders live in
   `subprocess_utils`; the up/health/down/failure/cleanup sequencing lives in
   `cli/logic/demo/isolation.py` (confirmed, matches row 6 above). No compose sequencing in a
   shared module.
3. **Schema source for D4:** row 7 above references the canonical root `schema.sql` through
   the installer's bootstrap mechanism — not a demo-specific copy, not read from the invoking
   checkout at execution time.
