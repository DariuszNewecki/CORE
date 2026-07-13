---
kind: planning
title: core-cli 1.0.0 Smoke Test — Follow-up Actions
status: draft
---

# core-cli 1.0.0 Smoke Test — Follow-up Actions

Tracks the actions arising from the 2026-07-12 `core-cli 1.0.0` release smoke test
(see `CORE-CLI-Release-Smoke-Test.md`, graded **SHIP** after fixes). Checked items
are done and verified; unchecked items are pending, each with the exact command and
who should run it.

---

## Done (verified 2026-07-12)

- [x] **`core-runtime 2.9.0` published to PyPI.** Fixes the stale `CoreApiClient`
  surface. Verified: PyPI latest = `2.9.0`; fresh `pip install core-cli` on the test
  VM pulled it and all commands passed. Commit `c29b9ae5`, tag `v2.9.0`.
- [x] **GitHub Release `v2.9.0 — CLI Client Parity` created.** Releases page now shows
  2.9.0 as Latest (the PyPI publish workflow does not auto-create GitHub Releases —
  they are a separate `gh release create` step).
- [x] **Dev `.venv` repaired.** A stray `core-runtime 2.8.0` wheel was shadowing the
  editable `src/`; `pip install -e .` restored `src/` as the import source.
  `core-api` + `core-daemon` restarted clean on current code; `/v1/analysis/bridges`
  serves 200.
- [x] **`core-cli 1.0.1` published to PyPI, pinned to `core-runtime>=2.9.0`.** Tag
  `v1.0.1` (`a0baa1c`) → CI publish via OIDC. Verified: PyPI core-cli = `1.0.1`,
  `requires_dist` includes `core-runtime>=2.9.0`. GitHub Release
  `v1.0.1 — Runtime Pin` created.
- [x] **CORE `main` pushed** through `c14a54fc` (run-log doc updated to SHIP).

---

## Done (continued, 2026-07-12)

- [x] **Smoke-test doc command drift fixed.** Removed `core code integrity`
  (nonexistent); corrected Phase 4 to `docstrings` / `format-imports`; added a Phase 4
  scope warning (those commands mutate the instance's own repo).
- [x] **Phase 5 BYOR `[WRITE]` apply steps exercised** (core-cli 1.0.1 + runtime 2.9.0).
  `onboard --write --stage` and `promote` write a full `.intent/` floor; `scout --write`
  induces real rules. Details + findings F-1/F-2/F-3 in the smoke-test doc's
  "Phase 5 write-flow exercise" section.
- [x] **`core-runtime 2.9.1` published to PyPI** (F-1/F-2 fixes + `docs/byor-quickstart.md`
  rewrite + `CORE_API_URL` wiring — see F-1/F-2 entries above and CHANGELOG.md `[2.9.1]`).
  Commit `5a5c6277`, tag `v2.9.1` → CI publish via OIDC, verified green
  (`gh run` `29191796948`, 1m17s). Verified: `pip index versions core-runtime` shows
  `2.9.1`. GitHub Release `v2.9.1 — BYOR Write-Flow Fixes` created. `core-cli 1.0.1`
  already pins `core-runtime>=2.9.0`, so it picks this up on the next install/upgrade
  with no core-cli-side change needed.
- [x] **Full same-host BYOR walkthrough run live on a fresh VM (2026-07-12).**
  Genuinely fresh Ubuntu 24.04 LXC (no prior CORE install): `pip install
  core-cli` (1.0.1 + core-runtime 2.9.1) + a from-source `core-api` (Postgres
  + Qdrant via Docker Compose) on the same host. Full walkthrough passed:
  onboard → scout (offline 4-rule menu) → audit PASS → violation → audit FAIL
  (correct 2 BLOCK findings) → fix → audit PASS. VM access procedure written
  up as `.specs/planning/CORE-CLI-VM-Test-Access-Runbook.md` after burning
  time on ad-hoc SSH-key guessing first.
- [x] **F-4 (new, found live) — relative-path resolution bug — fixed
  2026-07-12.** `onboard`/`promote`/`scout` sent `path` as a plain string
  over HTTP with no client-side resolution; a relative path (`.`) was
  resolved by whichever process received it — for `onboard`/`promote` that's
  the CORE API server, not the CLI. `core project onboard .` silently
  targeted the *server's* cwd. Confirmed live: onboarding `.` resolved to the
  CORE API's own repo (correctly refused via the existing-`.intent/` guard);
  on a clean target it would have silently onboarded the wrong location with
  no error. Fixed in `core-cli` (`onboard.py`, `scout.py`): `path` now
  resolves to absolute before being sent. Also fixed a stale hint string
  (`core-admin project onboard promote` → `core project promote`) and a
  README gap (`promote` was missing from the commands table). 4 new tests,
  full 54-test suite passes. `docs/byor-quickstart.md` corrected to always
  use absolute paths, plus two more bugs found in the same live pass: wrong
  schema path (`infra/sql/db_schema_live.sql` doesn't exist; real path is
  `schema.sql`) and `core-admin daemon up` assuming systemd units that a
  fresh clone doesn't have.
- [x] **`core-cli 1.0.2` published to PyPI.** Tag `v1.0.2` → CI publish via
  OIDC (lint + typecheck + test + build + publish, all green). Verified:
  `pip index versions core-cli` shows `1.0.2`. GitHub Release
  `v1.0.2 — Path Resolution Fix` created.

---

## Pending

### 1. BYOR write-flow findings (F-1/F-2/F-3 from the Phase 5 exercise)
- [x] **F-1 (topology) — closed 2026-07-12, option (a).** `project
  onboard/promote/scout --write` are **API-host-filesystem** operations; `path`
  resolves and writes on the CORE API host, not the caller's machine. This is
  not an open design choice — ADR-054 D3 already binds `core-api` to loopback
  only, single-operator, no auth, and explicitly gates any non-loopback
  exposure behind a future dedicated ADR with bearer-token auth as a
  prerequisite. A content-upload path (option b) would mean letting an
  unauthenticated remote client direct writes into an arbitrary server-side
  path — exactly what D3 forecloses. So co-location (or an SSH tunnel that
  makes "remote" loopback again, as this smoke test used) is documented as the
  required model for Phase 1; a genuine remote-write path is deferred until
  the D3 auth-promotion ADR lands, at which point `core-cli`'s pure-HTTP
  consumer design (ADR-146 D2) can carry it without further protocol changes.
  Documented in the `onboard`/`promote` API docstrings
  (`src/api/v1/project_routes.py`).

  **Follow-on discovered while documenting this (2026-07-12):**
  `docs/byor-quickstart.md` had been silently broken for 5 days — commit
  `608d8f72` (2026-07-07, ADR-146 extraction) removed `onboard`/`scout` from
  `core-admin`, but the quickstart still told readers to `pip install
  core-runtime` and run `core-admin project onboard . --write` /
  `core-admin project scout . --write`. Neither command exists anymore; the
  replacement is `pip install core-cli` (transitively installs
  `core-runtime`) then `core project onboard`/`scout`. Rewritten with the
  correct command surface, the real infra requirement (onboard/scout always
  need a reachable `core-api`, contra the doc's old "no Postgres, no Qdrant"
  claim — only `core-admin code audit --offline` is genuinely infra-free),
  and the write-locality asymmetry (`onboard`/`promote` write server-side;
  `scout`'s ratified rules write client-side).

  Also fixed in the same pass: `CoreApiClient` (`src/api/cli/client.py`)
  advertised `CORE_API_URL` as a way to point the CLI at a remote host (in
  `core-cli`'s README and this doc's own smoke-test prerequisites) but never
  actually read the env var — every call site does `CoreApiClient()` with no
  args, so it silently always used the hardcoded `127.0.0.1:8000` default.
  Today's smoke test only "worked" cross-host because of an SSH reverse
  tunnel making the remote `localhost:8000` proxy back to loopback, not
  because `CORE_API_URL` did anything. Fixed: `__init__` now resolves
  `base_url` → `CORE_API_URL` env var → loopback default, in that order.
  Tests in `tests/api/cli/test_client.py`.

  **Still open, NOT fixed this pass (flagged, not touched):**
  `docs/getting-started.md`'s "Govern your own repo (BYOR)" table and callout
  (and `README.md`'s BYOR mention) have the *identical* staleness —
  `core-admin project onboard/scout` and the "works from a plain `pip install
  core-runtime`" claim. Same root cause (commit `608d8f72`), same fix shape,
  different files. Also found: `core-cli`'s own `onboard.py` prints a stale
  hint (`core-admin project onboard promote {path}`, should be `core project
  promote {path}`), and `core-cli`'s `README.md` doesn't document `promote`
  at all. Both are in the separate `core-cli` repo — out of scope for edits
  from this repo without separate authorization.
- [x] **F-2 (error handling) — fixed 2026-07-12.** `initialize_repository` and
  `promote_staged` (`src/cli/logic/byor.py`) now wrap their `mkdir`/`shutil.copy2`
  target writes in `try/except OSError`, logging the real cause and raising
  `typer.Exit(code=1)` — the same idiom every other failure path in the file already
  uses. `project_routes.py` already mapped `SystemExit` → `HTTPException(400, ...)`,
  so this closes the leak without touching the API layer: the raw `OSError` (and its
  absolute path) no longer reaches the HTTP response body as a 500; the operator sees
  the real reason in CORE logs. Same fix covers `onboard` (`initialize_repository`
  shares the pattern); `scout` was confirmed unaffected — its API route never writes
  to disk. Tests added in `tests/cli/logic/test_byor_stage.py`
  (`test_initialize_repository_raises_typer_exit_on_oserror`,
  `test_promote_staged_raises_typer_exit_on_oserror`).

  **Correction, found via live re-verification (2026-07-12, same day):** the
  first pass of this fix did not actually work end-to-end — confirmed by
  restarting `core-api` and hitting `POST /v1/project/onboard` against a
  permission-denied path (`/root/...`), which still returned a raw-detail 500.
  Two bugs, both now fixed:
  1. The `OSError` was leaking from `target_intent.exists()` (the pre-write
     overwrite-guard check), not just the `mkdir`/`copy2` write loop —
     `Path.exists()` re-raises `PermissionError` rather than swallowing it.
     Both call sites (`initialize_repository`, `promote_staged`) now wrap that
     check the same way. Regression tests:
     `test_initialize_repository_raises_typer_exit_on_existence_check_oserror`,
     `test_promote_staged_raises_typer_exit_on_existence_check_oserror`.
  2. **Pre-existing bug, older than this fix:** `typer.Exit` is
     `click.exceptions.Exit` → `RuntimeError` → `Exception` in the installed
     Typer (0.16.1) — it is **not** a `SystemExit` subclass. `project_routes.py`'s
     `except SystemExit` branch in `onboard_project`/`promote_onboard` had
     never actually caught it, so *every* known `byor.py` failure mode (missing
     stage, existing `.intent/`, not just this OSError case) has always fallen
     through to the generic `except Exception` → 500 branch. Fixed: both
     routes now catch `(SystemExit, typer.Exit)`. A pre-existing test
     (`test_promote_returns_400_on_typer_exit` in
     `tests/api/v1/test_project_routes.py`) already asserted the correct
     behavior but had never actually been run (pytest is a governor action) —
     it would have failed against the old code. Added the missing symmetric
     `test_onboard_returns_400_on_typer_exit`.

  Verified live against the restarted `core-api`: permission-denied onboard
  now returns a clean 400; a genuine write still succeeds 200; re-onboarding
  an already-`.intent/`-having path now returns 400 (previously 500, same
  root cause). Lesson: authored-but-unexecuted tests are not verified tests —
  the bug shipped despite a correct-looking test already existing for it.
- **F-3 (automation):** `scout` has no batch-accept (Scout D5, by design) — blocks
  automated/CI onboarding of induced rules. Confirm this is the intended posture.

### 2. Phase 4 `code format/format-imports --write` — deliberately un-exercised
These mutate the CORE **instance's own** repo (no repo argument), so `--write` against
the dev instance would dirty `/opt/dev/CORE`. Exercise only against a disposable
instance pointed at a throwaway `REPO_PATH`, or accept + commit the diff knowingly.

### 3. ✅ Done (with a correction) — `.env` loading backstop via systemd `EnvironmentFile`
**Correction:** the JWT boot guard that motivated this item was already removed from
OSS CORE in `dab0187c` (2026-07-07, UAC/JWT extracted to core-platform). Current `src/`
has **zero** `JWT_SECRET_KEY` references, and v2.9.0 ships without it — CORE is the
auth-free loopback runtime (ADR-054 D3). The boot failure seen on 2026-07-12 was the
**stale 2.8.0 wheel's** guard, not current code. So there is no live JWT pre-flight to
protect.

The fix applied is still valid on its **real** merit: systemd drop-ins
`~/.config/systemd/user/{core-api,core-daemon}.service.d/env.conf` add
`EnvironmentFile=-/opt/dev/CORE/.env`, which backstops **all** `.env` config
(`DATABASE_URL`, `QDRANT_URL`, LLM settings) against the `parents[2]` `REPO_ROOT`
fragility — if the app-level `load_dotenv` ever resolves the wrong root (wheel-shadow
scenario), systemd has already injected the config via an absolute path. `.env` verified
systemd-parse-clean; injection proven with a transient unit; zero live-service
disruption. Deeper root fix (the `parents[2]` pattern, which also affects `.intent/`
discovery under wheel installs) remains separate — see memory
`feedback_parents_n_package_path_antipattern`. Dev `.env` still carries a now-dead
`JWT_SECRET_KEY` line (harmless; governor may prune).

### 4. ✅ Done — `MEMORY.md` hot/cold tiering
Diagnosed: the index had no cap on entry *count* (238 durable pointers ≈ 40 KB),
so sections H/I/J/K were silently dropped past the ~24 KB auto-load cap. Fixed with
option-A tiering seeded by a B-pass: split into a **54-entry HOT index** (9.6 KB,
every-task ambient norms — under the 17 KB target) and **`reference_index.md`**
(184 subsystem-specific lessons, not auto-loaded; still recalled by each file's
`description`). Zero entries lost. Memory repo commit `1c3ca0a`. Future lessons that
need a trigger to be relevant go to the cold tier, keeping the hot index bounded.

---

## Notes for the next smoke run

- Reverse tunnel from `.22`: `ssh -R 8000:localhost:8000 core-cli@192.168.20.46`
  using `~/.ssh/core_cli_smoke` (persistent key). `core-api` stays loopback-bound
  (ADR-054 D3 clean).
- Test VM `.46` has `~/core-test-fresh` (core-cli 1.0.0 + core-runtime 2.9.0) and a
  throwaway `~/smoke-testrepo`. After publishing 1.0.1, `pip install -U core-cli` in
  that venv to re-verify.
