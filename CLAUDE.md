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
- Ask before pushing, running the full test suite, or anything touching the live DB or daemon.
- Change tests together with the code they cover.
- Stage files by name; don't commit other people's uncommitted work.
- Temporary files go in `var/tmp/`.
