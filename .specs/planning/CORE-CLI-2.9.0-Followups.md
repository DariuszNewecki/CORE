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

### 3. `core-api` systemd `JWT_SECRET_KEY` durability — governor, low priority
The `core-api.service` unit has **no `EnvironmentFile`**. Startup only gets a real
`JWT_SECRET_KEY` because the app itself calls `load_dotenv(REPO_ROOT/".env")`. This
works today, but a systemd start with a different working directory (or a future
refactor that drops the app-level `load_dotenv`) would fail the security pre-flight
(`JWT_SECRET_KEY is set to the insecure default`). Consider adding
`EnvironmentFile=-/opt/dev/CORE/.env` to the unit as belt-and-suspenders. (`.env`
itself already holds a strong 64-char secret — no secret rotation needed.)

### 4. `MEMORY.md` deeper compaction — housekeeping
The auto-loaded memory index was trimmed (removed 36 stale `Session state` lines,
46.8 → 40.1 KB) but is still over the ~17 KB load limit, so it loads truncated.
Reaching the target needs curating the durable `feedback_*`/`reference_*` entries
(merge/shorten hooks), which is judgment work best done deliberately.

---

## Notes for the next smoke run

- Reverse tunnel from `.22`: `ssh -R 8000:localhost:8000 core-cli@192.168.20.46`
  using `~/.ssh/core_cli_smoke` (persistent key). `core-api` stays loopback-bound
  (ADR-054 D3 clean).
- Test VM `.46` has `~/core-test-fresh` (core-cli 1.0.0 + core-runtime 2.9.0) and a
  throwaway `~/smoke-testrepo`. After publishing 1.0.1, `pip install -U core-cli` in
  that venv to re-verify.
