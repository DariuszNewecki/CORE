# CLAUDE.md — CORE

## Freeze until 2026-10-29

v3 done = issues #1055, #1070, #1081, #1114, #1115, #1237, #1239, #1243, #1252,
#1255, #1285 (added 2026-10-23: found by the #1070 drill). Work only on these. No new reviews. Anything newly found is filed in
milestone CORE 3.1 unless it breaks one of these issues or a v3 gate. New
infrastructure (timers, crons, credentials, services) needs the governor's yes
first. The PR check `freeze-scope` refuses a PR whose description names none of
these issues and no CORE 3.1 issue.

CORE is a Python runtime that audits a codebase against rules in `.intent/`, records
violations in PostgreSQL, proposes fixes, and logs the chain from finding to commit.

## Layout

```
src/api/     FastAPI routes; DB access only via api/dependencies.py
src/body/    atomic actions, services, workers (execution)
src/mind/    rule engines; read .intent/, no I/O or execution
src/will/    agents and autonomous orchestration
src/shared/  common substrate; must not import mind/body/will
src/cli/     Typer commands; Rich rendering only here
.intent/     rules and config the runtime reads (YAML/JSON)
.specs/      design history (ADRs, papers); reference, not instructions
```

## Facts (update when they change)

- PyPI: `core-runtime` 2.15.2 (2026-10-19).
- Latest proof run: 6 (#1053, 2026-10-19, on 2.15.2); zero new proof issues, #1053 closed (v3 gate 1 met).
- Credentials: a closed list (governor 2026-10-23). No new token, no permission
  change, never asked of the governor. A job uses one of these and checks it at
  start, failing loudly if it does not work.
  - core-claude-bot gh login (core-claude; scopes repo, workflow, read:org):
    pushes branches, opens PRs into main and turns on their auto-merge,
    creates `promote/<sha>` branches, opens or updates the promotion PR, and
    closes a superseded one and deletes its branch. After
    review finding F2: also opens the PR for CORE's generated tests. The 06:00
    job hands this login's token to `promote propose` as `CORE_GITHUB_TOKEN`.
    Every 15 minutes `infra/scripts/core_alert_check.py` opens and closes the
    `[alert]` issues that mention the governor (review F4); no new credential.
  - CORE's own token (CORE daemon): read as `CORE_GITHUB_TOKEN` from the
    environment, else the unit credential `github-token`
    (`delivery_branch.py`). Pushes CORE's branches; cannot open PRs (#1252).
    Same variable name as above, a different credential.
  - `/etc/core/pipeline-github-token` (core-runner): an issues-only token on
    the governor's own account (#1198); it opens the issue for a failed
    promotion, and every other pipeline read is unauthenticated. GitHub sends
    no email for one's own issue, so an alert meant to reach the governor is
    opened as core-claude-bot (#1201 was opened as the governor).
  - `/etc/core/pipeline-deploy-key` (core-runner): the write deploy key; moves
    `live`. Ruleset `live-writers` lets any write deploy key do so; this is
    the only one (governor counted, 2026-10-23), and it stays the only one.
  - Deliberately not on the list: the governor's own GitHub login, the
    built-in `GITHUB_TOKEN` of Actions jobs, and PyPI (Trusted Publishing, no
    stored token).

## Commands

```
make install                          # poetry install
poetry run pytest tests/path -q       # run the tests you touched
poetry run ruff check <files>         # lint what you touched
poetry run core-admin code audit --offline
poetry run core-admin law check-tree  # validate .intent/ and .specs/
```

## Rules that fail CI

- Every public `def`/`class` in `src/` has a `# ID: <uuid4>` comment above it
  (`hooks/check_symbol_ids.py`); private `_names` are exempt.
- Layer boundaries above; the full list is in `.intent/rules/`.
- `@atomic_action` functions return `ActionResult` and accept `**kwargs`.
- `from __future__ import annotations` in every file; log via `shared.logger.getLogger`.

## Working here

- Ask before editing `.intent/` or `.specs/`.
- Ask before running the full test suite, or anything touching the live DB or daemon.
- Change tests together with the code they cover.
- Stage files by name; don't commit other people's uncommitted work.
- Temporary files go in `var/tmp/`.

## Working rules

- Fixes on a branch that touch only `src/`, `tests/` or `infra/` scripts, within
  the freeze above: do them and report afterwards. A fix needs no permission;
  new infrastructure (timers, crons, credentials, services) is not a fix and
  needs the governor's yes first.
- Everything the governor must act on goes in one list: at most once a day, at most 3 items.
- Never push while CI is red.
- Main is integration and not live (ADR-171 promotion flow, ruleset switched
  2026-10-18): core-claude's PRs merge themselves when the required checks are
  green. The governor approves only the daily promotion PR (a main SHA
  fast-forwarded to `live`), never a PR into main; only an approved promotion
  runs live. Never tell the governor a PR waits for their merge or approval.
- When main has green merges that are not live, open or update the promotion PR
  (`promote/<sha>` → `live`) with `core-admin promote propose`'s summary, as
  core-claude-bot: at most once a day, plus urgent ones on the governor's request.
- Never wait for CI in the foreground. After opening a PR, turn on auto-merge
  (`gh pr merge --auto --merge`), watch CI in the background, take the next task.
  Report a PR only when its CI goes red.
- Record decisions in the commit message, not in new documents.
- Reports: outcome first, at most 5 lines, no narration.
- Never ask the governor to approve law or CLAUDE.md text in chat: open the PR;
  the promotion that carries it is the approval.
- Never ask whether to proceed with work the governor asked for, or whether to push
  your own branch: run the offline audit, push, open the PR. Fix red CI before reporting.
- Branch work happens in a worktree under `var/tmp/wt-*`. Read-only git, `gh` and
  `core-admin` status queries need no permission.
- The governor decides only: design and policy choices, pushes or releases outside a PR,
  credentials, live-database writes, and stopping running processes.
- A release needs a named consumer: a proof run, or a user who needs the fix. The release
  request names that consumer and lists every change since the last release. No release
  for a single fix unless it breaks an installed user. One release per proof run, not per
  fix. The governor's "go" is the approval.

## What we measure (governor 2026-10-18)
Every task and PR serves at least one of these; say which in the PR's first line after any "Host change:".
1. Features vs gap fixes (no new features until v3)
2. Infra issues closed
3. Tests written autonomously by CORE
4. Bugs fixed
5. Progress to CORE goals (v3 gates)
6. Maturity
7. Robustness
8. Product vs factory time: prefer product work
9. Incidents: log every one, and anything needing manual hands
10. Ceremony: a control that does not block, undo, or alert is removed, not added
