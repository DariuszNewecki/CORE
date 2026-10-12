# D2 release runtime — units and deploy (ADR-132 D10 · D2, C6)

Prepared, not installed. Installing these and running the first deploy are governor acts
(ADR-132 D10.8: "deployment is an act performed by the governor"). The live switch also waits
on ADR-170 Stage 1 (`core-law`), because the services read their law from `/opt/core/law`,
which only `core-law` writes (ruling A).

Design: ADR-132 D10 · D2.

## Files

| File | Installed as | Owner / mode |
|---|---|---|
| `core-daemon.service`, `core-api.service`, `core-daemon-worker@.service` | core's user units (`~core/.config/systemd/user/`) | not writable by the assistant |
| `core.env.example` | `/opt/core/etc/core.env` | `core:core 0600` |
| `deploy.conf.example` | `/opt/core/etc/deploy.conf` | `root:root 0600` |
| `../../core-deploy` | `/usr/local/sbin/core-deploy` | `root:root 0755` |

The units stay `core`'s user units, which D10.8 allows ("or remain `core`-user units"), so
`core-admin daemon up/down/restart/status` keeps working through the existing services wrapper.
They differ from today's units in three ways:
- they run `/opt/core/current/venv/bin/python -I -m ...`, never the development tree (R1, R2);
- the working directory is `/opt/core/run`;
- exit 78 (a startup gate refused) does not restart-loop.

## Root script checklist (one script, later; listed here so nothing is missed)

1. Accounts: `core-build`, a system account with no login, outside `core-dev`, unable to read
   `/opt/core/etc`.
2. Directories: create `/opt/core/{releases,run,etc,build,backups}` with the modes in the
   design's layout table (`run` is `core:core 700`; `build` is root-owned and traversable;
   `/opt/core` itself is `root:root 755`).
3. CORE's clone: clone `/opt/core/repo` as `core` with `--no-hardlinks` and a sparse checkout
   that excludes `.intent/`, `.specs/`, `CLAUDE.md` and `.claude/`. Set `.git` to group
   `core-dev`, readable but not writable by the group, with `core.sharedRepository=0640`.
4. Law: done by ADR-170 Stage 1, before this script: `infra/core-law-setup` creates `core-law`,
   its venv and key, and seeds `/opt/core/law/{.intent,.specs}` owned by `core-law`.
5. Secrets: `/opt/core/etc/secrets.env` (`core:core 0600`) holds `DATABASE_URL`,
   `CORE_MASTER_KEY` and the API keys. It is named by `CORE_SECRETS_FILE`, never by
   `EnvironmentFile`.
6. Units: install the three units, remove the old `core-daemon.service.d/env.conf` drop-in
   (it exported `/opt/dev/CORE/.env`), then `daemon-reload`.
7. Deploy: install `core-deploy`, then run `sudo core-deploy <tag>` for the first release.
8. The assistant's side: add `safe.directory=/opt/core/repo/.git` to `core-claude`'s own git
   config, then fetch `core/develop` from the clone.

## What `core-deploy` guarantees (tested in `tests/infra/test_core_deploy.py`)

- git runs only as `core`, in CORE's clone, with D1's safe options. Build backends run only
  as `core-build`. root installs wheels only, with `--no-index` and lock hashes.
- The CORE wheel is accepted only if every file in it is byte-identical to `src/` in the
  archive, its console scripts match `pyproject.toml`, and it contains no `.pth` file.
- A commit is refused unless it is on upstream `develop` and its CI is green.
- A failure before the switch changes nothing live. A failure after the switch, with no
  migration, switches back.
- After a migration, any failure stops (exit 3) and the governor decides. The old release is
  never restarted against a migrated schema.
- `--rollback` refuses when a migration lies between the two releases.

Known limit: the post-switch heartbeat check reads `GET /v1/daemon/status`. When
`require_governor` goes live (D10.11 step 4), that check needs its own read-only channel.
