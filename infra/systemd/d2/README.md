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

## Installing (one root session, with the sandbox)

`infra/core-runtime-setup` does every step: the accounts, `/opt/core`, CORE's clone, the
configuration, `core-deploy`, the sandbox units and these units. Its docstring lists each step,
owner and mode. Every file it installs is fetched from GitHub at the commit you name, so root
installs exactly the pushed bytes. `--ref` is a full commit sha on `develop` whose CI is green.

```
cd /opt/dev/CORE
sudo infra/core-runtime-setup --ref <sha>            # plan: prints every change, makes none
sudo infra/core-runtime-setup --ref <sha> --apply    # does it, then runs its probes
sudo core-deploy <sha>                               # the first release goes live
```

The script reloads the units but does not restart them: the services keep running today's code
until `core-deploy` switches to the release and restarts them. Run the three commands in one
session. Afterwards, the assistant adds `safe.directory=/opt/core/repo/.git` to its own git
config.

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
<!-- probe: host-change-stated must block; this PR is closed unmerged -->
