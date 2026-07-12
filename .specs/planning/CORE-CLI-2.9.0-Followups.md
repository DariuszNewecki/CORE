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

## Pending

### 1. Fix smoke-test doc command drift — safe, mechanical
`CORE-CLI-Release-Smoke-Test.md` (Phases 3–4) names commands that don't match the
shipped CLI:
- `core code integrity` — **does not exist**; remove it.
- Phase 4 uses `fix-docstrings` / `fix-imports`; the real commands are
  `docstrings` / `format-imports`.

Already noted in the run-log Outcome; the Phase 3/4 tables above it still show the
old names. A `.specs/` edit (governed).

### 2. Exercise Phase 4.2–5.4 `[WRITE]`-apply steps — future smoke run
The smoke test ran every read path and every `[WRITE]` **dry-run**, but the
`--write` / `--stage` / `promote` apply steps were not executed (grade was already
settled, and the paths are proven reachable). A follow-up run against a throwaway
repo can exercise the apply side end-to-end.

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
