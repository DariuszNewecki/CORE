# CLAUDE.md — CORE

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

- PyPI: `core-runtime` 2.15.1 (2026-10-19).
- Latest proof run: 4 (#1053, 2026-10-18, on 2.15.0); its friction is #1174-#1178.

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

- Fixes on a branch that touch only `src/`, `tests/` or `infra/` scripts: do them
  and report afterwards. Never ask permission for these.
- Everything the governor must act on goes in one list: at most once a day, at most 3 items.
- Never push while CI is red.
- Main is integration and not live (ADR-171 promotion flow, ruleset switched
  2026-10-18): core-claude's PRs merge themselves when the required checks are
  green. The governor approves only the daily promotion PR (a main SHA
  fast-forwarded to `live`), never a PR into main; only an approved promotion
  runs live. Never tell the governor a PR waits for their merge or approval.
- When main has green merges that are not live, open or update the promotion PR
  (`promote/next` → `live`) with `core-admin promote propose`'s summary, as
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
