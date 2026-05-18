# D6 Stage C — CLI Cutover Migration Plan

**Parent:** ADR-055 (API Phase 2 — /fix + /quality)
**Status:** ✅ Complete — landed 2026-05-18
**Date drafted:** 2026-05-18
**Date closed:** 2026-05-18

---

## Final results

**Outcome:** 23 of 23 in-scope D6 files migrated to `api.*` + `cli.*` only. `integrity.py` parked as planned (#353). One additional governance-debt regression filed during execution (#356). All acceptance criteria green.

### Acceptance summary

| Check | Result |
|---|---|
| `grep -E "from (body|will|mind)\." <23 D6 files>` | **0 hits** |
| `grep -E "from shared\." <23 D6 files>` (excl. `shared.cli.command_meta`, `shared.logger`) | **0 hits** |
| `ruff check <23 D6 files>` | **All checks passed** |
| `core-admin code audit --files <23 D6 files>` | **0 findings — PASS verdict** |
| integrity.py parked status | 1 carried import — tracked by #353 |
| #336 (ADR-055 Phase 2 tracker) | Already CLOSED — no posting needed |

### Commit ledger — 16 commits on `main`

| # | SHA | Type | Subject |
|---|---|---|---|
| 1 | `43b2adf1` | C0 prep | `chore(api): add _poll_run helper to CoreApiClient` |
| 2 | `84c0c0ec` | C0 prep | `chore(cli): relocate command_meta to shared.cli` |
| 3 | `c68b2538` | reopen #1 | `feat(api): extend RunFixRequest with params passthrough` |
| 4 | `35d27a50` | reopen #2 | `feat(body): register fix.body-ui, relocate from cli/logic to body/self_healing` |
| 5 | `d5004815` | **C1** | `refactor(cli): migrate Batch C1 — 8 code/* CLI files to api.* only` |
| 6 | `fcda79a9` | reopen #3 | `feat(api): extend RunFlowRequest with params passthrough` |
| 7 | `1b505da5` | **C2** | `refactor(cli): migrate Batch C2 — fix_ir.py + modularity.py to api.* only` |
| 8 | `6e6b1f8f` | reopen #4 | `feat(api): add POST /v1/quality/policy-coverage + relocate audit server-side` |
| 9 | `91e4060b` | **C3** | `refactor(cli): migrate Batch C3 — 4 commands/check/* files to api.* only` |
| 10 | `dc62f039` | reopen #5 | `feat(body): register fix.settings_access atomic action` |
| 11 | `9c398923` | **C4** | `refactor(cli): migrate Batch C4 — 7 commands/fix/* files to api.* only` |
| 12 | `43b5a297` | reopen #6 | `feat(body): register fix.capability_tagging + fix.vulture_heal; relocate vulture_healer` |
| 13 | `2e0456d9` | **C5a** | `refactor(cli): migrate Batch C5 part 1 — all_commands.py to api.* only` |
| 14 | `e15e06a1` | reopen #7 | `feat(body): register fix.purge_legacy_tags + fix.policy_ids` |
| 15 | `20d3295a` | **C5b** | `refactor(cli): migrate Batch C5 part 2 — metadata.py to api.* only` |
| 16 | `3eea5b87` | D unblock | `chore(intent): classify 6 new fix.* actions in action_risk.yaml` |

### Plan vs. actual

| Metric | Planned | Actual | Delta |
|---|---|---|---|
| Total commits | ~9 | **16** | +7 — every batch surfaced ≥1 Stage B reopen |
| Stage B reopens | 0 (allowed, not expected) | **7** | Pattern emerged: API request models + atomic-action registration |
| Files migrated | 23 | **23** | ✓ |
| LOC touched (approx) | ~1,500 | ~2,100 | Includes the 7 reopen commits |
| Registry growth | 0 (Stage C is CLI-only) | **+6 actions** (22 → 28) | Stage B reopens registered them |

### Carried-forward governance debt

| Issue | What | State |
|---|---|---|
| **#353** | integrity.py parked — needs `POST /v1/integrity/{baseline,verify}` | OPEN, blocked. Anticipated in plan §6. |
| **#356** | all_commands.py dropped db-registry step — needs `fix.sync_commands` action | OPEN. **New** during execution; not in original plan. |

---

## Lessons from execution

These observations matter for future D7+ batches (Phase 3 namespace migrations) and are also memorised under feedback notes.

1. **Every batch surfaced a Stage B reopen.** The plan treated reopens as a risk; they turned out to be the steady-state pattern, not exceptions. Two recurring shapes:
   - **API request model gaps** — actions accept kwargs the request schema doesn't carry (`RunFixRequest.params`, `RunFlowRequest.params`).
   - **Atomic-action registration gaps** — functions decorated `@atomic_action` without `@register_action`, or pure body services with no atomic wrapper at all. Six new actions registered across reopens #2/#5/#6/#7.

2. **`shared.cli.command_meta` was the right neutral home.** The plan offered `cli.utils.command_meta` (decision #2 default), but recon during execution surfaced a body importer (`command_sync_service.py`) that would have created a body→cli inversion. The `shared.cli.*` subpackage avoids the inversion and removes the false-positive class from the rule's grep test. New shape worth carrying forward for any "CLI-adjacent primitives shared with body introspection" need.

3. **`POST /v1/fix/all` (flow.fix_code) is NOT equivalent to the CLI's `fix all`.** They were closer in name than in scope — the canonical flow runs ~9 code-purity actions; the CLI was bundling ~11 broader-scope steps (DB sync, vector sync, IR scaffolds, capability tagging, etc.). Per-step migration was correct (risk #6 ratified). Issue #356 captures the one step that lost its bundle home.

4. **action_risk.yaml is a hidden coupling between body and `.intent/`.** Registering a new atomic action is a **two-step** operation: `@register_action` in `src/body/atomic/*` AND a classification row in `.intent/enforcement/config/action_risk.yaml`. The runtime refuses to boot if these drift apart (commit 16 — Stage D unblock). Future Stage B reopens that register actions must include the action_risk update in the same commit, OR be followed immediately by a governor-authorized classification commit before any audit invocation.

5. **The "dangerous" classification follows blast radius, not provenance.** Mechanical line-removers (`fix.purge_legacy_tags`) are `dangerous` for the same reason LLM-driven removers are: the operator can't recover without `git`. This refines the existing rubric — saved as feedback memory.

6. **Layer placement of relocated services matters per service.** During the relocate-or-keep decisions (commits 4, 12):
   - `body_ui_fixer.py`: relocated will/ → body/ (no will deps; was misplaced).
   - `vulture_healer.py`: relocated will/ → body/ (no will deps; was misplaced).
   - `capability_tagging_service.py`: **kept in will/** (genuinely depends on `will.agents.tagger_agent` + `will.orchestration.cognitive_service`). Body wrapper does a lazy `from will.*` import — body→will dep, but precedent already exists in `body/atomic/proposal_lifecycle_actions.py`.

7. **Stage A's `shared.logger` sweep was incomplete.** Decision #3 (fold-into-Stage-C) was correct — multiple batches found stale `from shared.logger import getLogger` lines that had to be migrated alongside the api.* cutover. Don't trust that a prior chore sweep was thorough.

---

## Where Stage C sits in D6

| Stage | What | Status | Commit |
|---|---|---|---|
| A | `shared.logger → stdlib logging` in CLI files touched by D6 | partial — see §6 | `98da9038` |
| B | 13 new `CoreApiClient` methods for `/fix` + `/quality` | done | `8f043e56` |
| **C** | **Cut over D6 CLI files to import only `api.*` + `cli.*`** | **this plan** | — |
| D | Drop suppress entries, run audit, close #336 | follows C | — |

Stage A built the typing-only foundation; Stage B built the client surface; Stage C is the actual file-by-file inversion. After Stage C, the 24 files in §2 must have **zero** imports from `body.*`, `will.*`, `mind.*`, or `shared.*` (per ADR-055 verification criterion #5).

API + client surface is ready — confirmed:
- Routes: `src/api/v1/fix_routes.py` (8 endpoints), `src/api/v1/quality_routes.py` (6 endpoints) match ADR-055 D2/D3.
- Client: 13 methods on `CoreApiClient` match (`run_fix`, `fix_all`, `fix_modularity`, `fix_ir`, `get_fix_run`, `quality_imports`, `quality_body_ui`, `quality_lint`, `quality_tests`, `quality_system`, `quality_gates`, `list_fix_commands`, `list_actions`).

No new routes or client methods are added in Stage C. If a migration reveals a missing endpoint, that's a Stage B reopen, not a Stage C scope creep.

---

## Scope — 23 files (24 in ADR-055 D6, minus `integrity.py` parked under #353)

ADR-055 D6 lists 22 files + `fix/fix_ir.py` + `fix/modularity.py` = 24. `integrity.py` is excluded from Stage C: `IntegrityService.create_baseline / verify_integrity` is not a quality-system check and has no matching D2/D3 endpoint. Issue #353 tracks the missing endpoint design. Including it in Stage C would force a mid-migration endpoint addition for one file, which is the wrong forcing function. Stage C ships at 23 files; ADR-055 D6 verification criterion #5 will need a footnote (or an ADR-055 amendment) acknowledging integrity.py is gated on #353 closure.

Counts below are direct `body|will|mind|shared` imports excluding `shared.logger` (lifted from §6 inventory in the prior turn).

### Batch C1 — leaf resources, single import (8 files) — ✅ landed `d5004815` (+ reopens `c68b2538`, `35d27a50`)

Lowest risk, smallest diffs. Each file is a thin command surface; the migration template from ADR-054 Phase 1 (`code/lint.py`, `code/audit.py`) applies directly.

| File | Direct imports | Target endpoint |
|---|---|---|
| `cli/resources/code/fix_atomic.py` | `shared.models.command_meta` | `POST /v1/fix/run/{fix_id}` |
| `cli/resources/code/format.py` | `body.self_healing.code_style_service.format_code` | `POST /v1/fix/run/fix.format` (atomic dispatch) |
| `cli/resources/code/docstrings.py` | `body.self_healing.docstring_service.fix_docstrings`, `shared.models.command_meta` | `POST /v1/fix/run/fix.docstrings` |
| `cli/resources/code/logging.py` | `shared.context`, `shared.models.command_meta` | `POST /v1/fix/run/fix.logging` |
| `cli/resources/code/actions.py` | `body.atomic.registry.action_registry`, `shared.models.command_meta` | `GET /v1/actions` |
| `cli/resources/code/check_imports.py` | `body.atomic.executor.ActionExecutor`, `shared.context` | `POST /v1/quality/imports` |
| `cli/resources/code/test.py` | `mind.enforcement.audit.test_system` | `POST /v1/quality/tests` |
| `cli/resources/code/check_ui.py` | `shared.context` (fn-local) | `POST /v1/quality/body-ui` |

`integrity.py` is **parked** under #353 — no matching endpoint exists. See §6.

### Batch C2 — composite resources / longer flows (2 files) — ✅ landed `1b505da5` (+ reopen `fcda79a9`)

Touch multiple endpoints or call `/fix/all`-style flows. Need careful exit-code passthrough.

| File | Direct imports | Target endpoint |
|---|---|---|
| `cli/commands/fix/fix_ir.py` | `shared.context` (+ another) | `POST /v1/fix/ir` (sync, returns path) |
| `cli/commands/fix/modularity.py` | `shared.context`, `will.self_healing.modularity_remediation_service` | `POST /v1/fix/modularity` (async, kind=modularity) |

### Batch C3 — `cli/commands/check/*` (4 files) — ✅ landed `91e4060b` (+ reopen `6e6b1f8f`)

| File | Direct imports | Target endpoint |
|---|---|---|
| `commands/check/quality.py` | `mind.enforcement.audit.{lint,test_system}`, `shared.action_types`, `shared.atomic_action` | `POST /v1/quality/system` |
| `commands/check/quality_gates.py` | `shared.infrastructure.intent.operational_config` (+1) | `POST /v1/quality/gates` |
| `commands/check/imports.py` | `body.atomic.check_actions.action_check_imports` | `POST /v1/quality/imports` |
| `commands/check/diagnostics_commands.py` | `shared.action_types.ActionResult` | client method TBD — see §5 risk #4 |

### Batch C4 — `cli/commands/fix/*` standalone (7 files) — ✅ landed `9c398923` (+ reopen `dc62f039`)

| File | Direct imports | Target endpoint |
|---|---|---|
| `commands/fix/atomic_actions.py` | `body.atomic.executor`, `body.self_healing.atomic_actions_fixer`, `shared.action_types`, `shared.atomic_action` | `POST /v1/fix/run/fix.atomic_actions` |
| `commands/fix/code_style.py` | `body.self_healing.header_service`, `shared.action_types`, `shared.atomic_action` | `POST /v1/fix/run/fix.code_style` (or .headers) |
| `commands/fix/handler_discovery.py` | `body.atomic.registry.action_registry` | `GET /v1/actions` (filter client-side) |
| `commands/fix/list_commands.py` | (only `shared.logger`, already on stdlib post-Stage A) | `GET /v1/fix/commands` — convert to client call |
| `commands/fix/imports.py` | `shared.action_types`, `shared.atomic_action`, `shared.utils.subprocess_utils.run_poetry_command` | `POST /v1/fix/run/fix.imports` |
| `commands/fix/body_ui.py` | `shared.activity_logging`, `shared.context` | `POST /v1/quality/body-ui` |
| `commands/fix/settings_access.py` | `body.maintenance.refactor_settings_access`, `shared.context` | `POST /v1/fix/run/fix.settings_access` |

(7 files — Batch C4 absorbs `list_commands.py` and `body_ui.py`.)

### Batch C5 — `commands/fix/{all_commands,metadata}.py` (the megaliths) — ✅ landed `2e0456d9` + `20d3295a` (+ reopens `43b5a297`, `e15e06a1`)

The two largest, most-coupled files. Each imports 12 modules across `body.*`, `shared.*`, and `will.*`. Migrate **last** — by the time we reach them, the atomic action dispatch (`POST /v1/fix/run/{fix_id}`) will be battle-tested across batches C1–C4, and these files are mostly orchestration over the same actions.

| File | Direct imports | Strategy |
|---|---|---|
| `commands/fix/all_commands.py` | 12 imports — `body.{introspection,maintenance,self_healing}.*`, `shared.context`, `shared.infrastructure.database`, `will.self_healing.capability_tagging_service` | Replace per-step body imports with sequence of `POST /v1/fix/run/{fix_id}` calls, or call `POST /v1/fix/all` if the curated flow matches. Preserve dry-run semantics via `write` flag. |
| `commands/fix/metadata.py` | 12 imports — five `body.self_healing.*` services, two `will.self_healing.*` services, `body.atomic.executor`, `shared.*` | Each `body.self_healing.*` call → corresponding `fix.*` atomic action via `POST /v1/fix/run/{fix_id}`. `will.*` services → confirm there is a matching `fix.capability_tagging`/`fix.vulture_heal` action; if not, that's a Stage B reopen (§5 risk #4). |

---

## Migration template (per file)

Identical to ADR-054 Phase 1 (`code/lint.py`, `code/audit.py`); use those as the reference implementations.

1. **Read the existing CLI file** to identify: command name, params (display vs. forwarded), exit-code rules, output format.
2. **Replace direct backend imports** with:
   ```python
   from api.cli import CoreApiClient
   ```
   and `CoreApiClient()` instantiation inside the command body.
3. **Strip Will/Body wiring** — execution moves server-side. If a `shared.context.CoreContext` was needed only to feed a Will service, drop it. If it was needed for display data, fetch via API.
4. **Keep display-only params client-side** — verbosity, severity filters, output format. These never round-trip to the server.
5. **Render `result` dict** with Rich/Console. Set exit code from `result.get("ok")` / `result.get("error")` / `result.get("status")`.
6. **For async endpoints** (202 + `run_id`): poll `GET /v1/fix/runs/{id}` until `status in {"completed", "failed"}`. Default timeout 300s matches the existing client pattern.
7. **For shared rendering types** (e.g. `AuditFinding`, `ComponentResult`): centralise in `cli/logic/*_renderer.py` so the CLI file only imports `api.*` and `cli.*`. Precedent: `cli/logic/audit_renderer.py::to_audit_finding`.
8. **Drop the suppress entry** in `.intent/...` (or `# audit: ...` comment) once the file is at zero violations.
9. **Verify** — see §4.

---

## Verification

Per ADR-055 Verification criterion #5, each file must reach **zero** `body|will|mind|shared` imports. Per-file checks:

1. `grep -E "^\s*(from|import) (body|will|mind|shared)\." <file>` returns **empty**.
2. `ruff check <file>` clean.
3. Smoke test the command end-to-end against a running `core-daemon`:
   - Sync endpoints: command runs, exit code matches pre-migration behavior, output renders.
   - Async endpoints: poll loop terminates, final status surfaces, exit code matches.
4. After all 24 files: `core-admin code audit --rule architecture.cli.api_only` reports zero findings attributable to D6 scope (ADR-055 verification criterion #6).

After every batch, request a manual `core-admin dev sync --write` if `DbSyncWorker` cadence hasn't caught up — but only at batch boundaries, not per file.

---

## Risks and call-outs — retrospective

Each risk is marked with what actually happened.

1. **Async polling helper.** ✅ **Pre-empted in C0** (commit `43b2adf1`). `_poll_run` on `CoreApiClient` was used by every async-dispatching CLI across C1–C5; the helper paid for itself immediately. Decision to add now (rather than dedupe in Stage D) was correct.

2. **`shared.logger` residue.** ✅ **Folded into each batch as planned.** Decision #3 stood. Several batches found more stale loggers than the prior recon predicted (lesson #7 below).

3. **`shared.models.command_meta` relocation.** ⚠ **Plan said `cli.utils`; executed as `shared.cli.command_meta`.** Recon during C0 found a body importer (`command_sync_service.py`) that would have created a body→cli inversion. New neutral home avoids the inversion. Lesson #2 captures the pattern.

4. **`diagnostics_commands.py` endpoint gap.** ✅ **Fired.** Stage B reopen #4 added `POST /v1/quality/policy-coverage` (commit `6e6b1f8f`). Helper `cli/logic/diagnostics_policy.py` rewritten as a thin client + render module.

5. **`metadata.py` will-service deps.** ✅ **Fired.** Stage B reopen #6 (commit `43b5a297`) registered `fix.capability_tagging` (lazy will import) and `fix.vulture_heal` (with `vulture_healer.py` relocation to body/). A further surprise: `metadata.py` also calls `purge_legacy_tags` and `add_missing_policy_ids` which weren't anticipated as missing — Stage B reopen #7 (commit `e15e06a1`) registered both as fix.* actions.

6. **`all_commands.py` collapse vs per-step.** ✅ **Per-step won.** The CLI's `fix all` and `flow.fix_code` diverged significantly (different scopes). Per-step migration kept most of the sequence; 3 steps (purge-legacy-tags, policy-ids, db-registry) had no registered action at the time. Reopen #7 restored purge-legacy-tags and policy-ids; db-registry remains dropped under **#356** (filed during execution).

7. **`fix/modularity.py` async-streaming UX regression.** ⚠ **Accepted.** Post-migration the CLI polls and shows final status only, not per-file progress. Documented in commit `1b505da5`. No follow-up filed; flagging here for future ADR-055 amendment if the regression becomes user-visible pain.

8. **Per-batch commit cadence.** ✅ **Held throughout.** Pre-commit hooks (ruff, ruff-format, yaml) caught format issues in 3 batches; standard pattern was "re-stage post-format, recommit same message". No --amend or --no-verify used.

### Unanticipated — surfaced during execution

9. **action_risk.yaml drift on every reopen that registered a new action.** Six new actions across reopens #2/#5/#6/#7 needed classification rows in `.intent/enforcement/config/action_risk.yaml`. The CLI refused to boot until commit `3eea5b87` added them. Should have been part of each reopen commit; lesson #4 above.

10. **Pre-existing `@atomic_action` layer leaks dropped during migration.** Several migrated files carried decorative-only `@atomic_action` decorations on CLI commands (never registered, never dispatched through executor). Found in: `fix_atomic_actions_cmd` (`fix.cli.atomic_actions`), `fix_headers_cmd` (duplicate `fix.headers`), `fix_imports_internal` (duplicate `fix.imports`), `fix_duplicate_ids_command` (`fix.duplicate`), `fix_placeholders_command` (decorative `fix.placeholders`), `tests_cmd` (`tests.cmd`). All dropped. Not a regression — these were pre-existing constitutional gaps that the migration exposed.

---

## Out of scope for Stage C

**Parked from D6 (in ADR-055 D6 list but excluded from Stage C):**

- `cli/resources/code/integrity.py` — `IntegrityService.create_baseline / verify_integrity` has no D2/D3 endpoint. Tracked by **#353** (`status:blocked`, `governance-debt`). Closes when a `POST /v1/integrity/{baseline,verify}` endpoint exists and `grep -rn "IntegrityService" src/cli/` returns zero. ADR-055 D6 verification criterion #5 needs a footnote (or ADR amendment) acknowledging this exception, otherwise Phase 2 cannot be marked complete.

**Outside D6 entirely (broader 111-file landscape from prior turn):**

- All `cli/commands/coverage/*`, `cli/commands/inspect/*`, `cli/resources/admin/*`, `cli/resources/context/*`, `cli/resources/database/*`, `cli/resources/symbols/*`, `cli/resources/vectors/*`, `cli/resources/workers/*` — these are Phase 3+ targets.
- `cli/commands/fix/audit.py` — explicitly deferred to Phase 3 per ADR-055 ("Deferred to Phase 3" section).
- Soft `shared.context` / `shared.models` imports in files outside the 23-file Stage C list — wait for the per-Phase ADR before touching.

If Stage C surfaces incidental cleanup in non-scope files, file an issue; do not in-line it.

---

## Open decisions for governor

**All five ratified 2026-05-18; defaults stand.** Notes attached where execution matters.

| # | Decision | Resolution |
|---|---|---|
| 1 | Add `_poll_run` helper to `CoreApiClient` now or after Stage C? | **Ratified: add now.** Lands in Stage C0. |
| 2 | Relocate `shared.models.command_meta` to `cli.utils` or allowlist? | **Ratified: relocate.** ⚠ Importers exist outside D6 scope — the C0 commit will touch non-D6 files. Commit message must name the reason explicitly ("relocate command_meta to cli.utils — CLI-layer metadata, not a domain model; removes a false-positive class from `architecture.cli.api_only`") so the wider-scope diff reads as deliberate, not drive-by. |
| 3 | Fold `shared.logger → logging` into Stage C diffs, or do a Stage A2 first? | **Ratified: fold into Stage C diffs.** |
| 4 | Batch commit cadence — per batch or per file? | **Ratified: per batch.** Five batch commits + C0 prep + C5 split = ~8 commits. |
| 5 | For `fix/all_commands.py`: collapse to `POST /v1/fix/all` or migrate per-step? | **Ratified: inspect at migration time; default per-step if any divergence.** |

---

## Suggested execution order — actual outcome

| Step | Plan | Actual | Notes |
|---|---|---|---|
| C0 prep | 2 commits | 2 commits | ✅ As planned. Relocation target shifted `cli.utils` → `shared.cli` mid-execution. |
| C1 | 1 commit | 1 commit + 2 reopens | Reopens #1 (`RunFixRequest.params`) + #2 (`fix.body-ui` registration). |
| C2 | 1 commit | 1 commit + 1 reopen | Reopen #3 (`RunFlowRequest.params`). |
| C3 | 1 commit | 1 commit + 1 reopen | Reopen #4 (`POST /v1/quality/policy-coverage`). |
| C4 | 1 commit | 1 commit + 1 reopen | Reopen #5 (`fix.settings_access` registration). |
| C5 | 2 commits | 2 commits + 2 reopens | Reopens #6 + #7 (4 atomic actions registered + 1 service relocation). |
| Stage D | 1 commit (close #336) | 1 unblock commit (`3eea5b87`) — #336 already CLOSED | action_risk classification gap (lesson #4); no suppress entries to drop. |
| **Total** | **~9 commits** | **16 commits** | +7 from Stage B reopens that became the steady-state pattern. |

**Final tally:** 16 commits, **23 files migrated** (24th — integrity.py — parked under #353), **+6 registered atomic actions** (22 → 28), **2 governance-debt issues** carrying forward (#353, #356).
