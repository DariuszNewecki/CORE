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

---

## Pending

### 1. BYOR write-flow findings (F-1/F-2/F-3 from the Phase 5 exercise)
- **F-1 (topology):** `project onboard/promote/scout` are **API-host-filesystem**
  operations; the remote-CLI → central-API topology can't write BYOR into a
  CLI-host-local repo. Decide whether to (a) document co-location as the required
  BYOR model, or (b) add a content-upload path so a remote CLI can onboard a local repo.
- **F-2 (error handling):** cross-host `promote` leaks a raw `OSError` as an
  `API error 500`. Should be a clean 4xx ("target path not accessible on the CORE host").
- **F-3 (automation):** `scout` has no batch-accept (Scout D5, by design) — blocks
  automated/CI onboarding of induced rules. Confirm this is the intended posture.

### 2. Phase 4 `code format/format-imports --write` — deliberately un-exercised
These mutate the CORE **instance's own** repo (no repo argument), so `--write` against
the dev instance would dirty `/opt/dev/CORE`. Exercise only against a disposable
instance pointed at a throwaway `REPO_PATH`, or accept + commit the diff knowingly.

### 3. ✅ Done — `core-api`/`core-daemon` `JWT_SECRET_KEY` durability
Root cause was subtler than "different CWD": the app loads `.env` via
`REPO_ROOT = Path(__file__).resolve().parents[2]` — which resolves to
`site-packages` if the code ever runs from a wheel copy (the 2026-07-12
shadow-wheel incident), leaving `.env` unloaded and the JWT security pre-flight
failing at boot. Fixed with systemd **drop-ins** (not touching the packaged units):
`~/.config/systemd/user/{core-api,core-daemon}.service.d/env.conf` adding
`EnvironmentFile=-/opt/dev/CORE/.env`. systemd injects the secret via an **absolute**
path, independent of where the code lives. `.env` verified systemd-parse-clean;
mechanism proven with a transient unit (systemd injects the real, non-default
`JWT_SECRET_KEY`). Applied with **zero live-service disruption** — takes effect on the
next natural start. Deeper root fix (the `parents[2]` `REPO_ROOT` fragility, which
also affects `.intent/` discovery under wheel installs) remains a larger, separate
item — see memory `feedback_parents_n_package_path_antipattern`.

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
