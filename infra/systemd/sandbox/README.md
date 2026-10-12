# Sandbox runner — units and root steps (ADR-132 D10.10, closes R4)

Prepared, not installed. Installing is a governor act. Design:
ADR-132 D10.10.

The units run the **release** (`/opt/core/current`), so the first `core-deploy` must
run before the check below.

## Files

| File | Installed as | Owner / mode |
|---|---|---|
| `core-sandbox.socket` | `/etc/systemd/system/core-sandbox.socket` | `root:root 0644` |
| `core-sandbox@.service` | `/etc/systemd/system/core-sandbox@.service` | `root:root 0644` |

They are **system** units, not `core`'s user units: `PrivateNetwork=` and the other
namespace walls need privileges that user units do not have on this host
(`apparmor_restrict_unprivileged_userns = 1`).

## Installing

`infra/core-runtime-setup` (see `infra/systemd/d2/README.md`) installs these units together with
the release runtime: the account `core-sandbox` (its own group only), the inbox
`/opt/core/repo/var/tmp/sandbox-inbox` (`core:core-sandbox 2750`), the two units, and the socket
enabled and started. `CORE_SANDBOX_MODE=service` comes with `core.env`.

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
