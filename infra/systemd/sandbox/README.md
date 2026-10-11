# Sandbox runner — units and root steps (ADR-132 D10.10, closes R4)

Prepared, not installed. Installing is a governor act. Design:
`var/reports/adr132-d10-10-sandbox-runner-design-20261011.md` (consolidated draft).

The units run the **release** (`/opt/core/current`), so the D2 release runtime
(`infra/systemd/d2/README.md`) must be installed first, in the same root session.

## Files

| File | Installed as | Owner / mode |
|---|---|---|
| `core-sandbox.socket` | `/etc/systemd/system/core-sandbox.socket` | `root:root 0644` |
| `core-sandbox@.service` | `/etc/systemd/system/core-sandbox@.service` | `root:root 0644` |

They are **system** units, not `core`'s user units: `PrivateNetwork=` and the other
namespace walls need privileges that user units do not have on this host
(`apparmor_restrict_unprivileged_userns = 1`).

## Root steps (after the D2 checklist)

1. Account: `useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin core-sandbox`.
   It is in no other group: not `core`, `core-dev`, `docker` or `sudo`.
2. Inbox: `install -d -o core -g core-sandbox -m 2750 /opt/core/repo/var/tmp/sandbox-inbox`.
   The setgid bit makes every snapshot `core` writes group `core-sandbox`, readable but not writable by
   the job. `core-sandbox` must be able to traverse `/opt/core`, `/opt/core/repo`, `.../var` and
   `.../var/tmp` (mode `o+x`); it must not be able to read `/opt/core/etc`.
3. Units: copy the two files, `systemctl daemon-reload`, `systemctl enable --now core-sandbox.socket`.
4. Mode: `CORE_SANDBOX_MODE=service` in `/opt/core/etc/core.env` (read by callers from M2 on).

## Verification (M1)

As the governor (`darek`), from any directory:

```
sudo -u core bash -c 'set -a; . /opt/core/etc/core.env; /opt/core/current/venv/bin/core-admin runtime sandbox-check --mode service'
```

Expected: every row `passed`, isolation `service`:
`ordinary`, `secrets`, `secret_link`, `tcp`, `host_sockets`, `new_socket`, `inbox_read_only`, `leftover`.

Fail closed:

```
sudo systemctl stop core-sandbox.socket
sudo -u core bash -c 'set -a; . /opt/core/etc/core.env; /opt/core/current/venv/bin/core-admin runtime sandbox-check --mode service'
sudo systemctl start core-sandbox.socket
```

Expected while stopped: every row `not_run`, reason "sandbox service unavailable" (the command
exits 1 because nothing passed — that is the point).

Peer check: the same command as `core-claude` (not `core`) cannot even connect (socket group
`core`), and a connection from any uid other than `core` is refused by the server.

R4 stays open after M1: it closes only when every repository-execution path in the design's
inventory runs through this runner (M2) and the law records it (M3).
