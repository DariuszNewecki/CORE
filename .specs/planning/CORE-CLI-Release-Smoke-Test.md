# core-cli 1.0.0 — Release Smoke Test

**Purpose:** End-to-end validation of `core-cli 1.0.0` on a vanilla Ubuntu VM against a
running CORE instance. Executed by Claude Code with direct VM access. The governor's job
is to hand over SSH access and approve any `--write` steps explicitly.

**Scope:** install → connect → read commands → write commands → BYOR flow.
Write-destructive steps are marked `[WRITE]` and require explicit governor confirmation
before execution.

---

## Run log

**Status as of 2026-07-12: paused mid-Phase 2.** Phase 1 fully passed. Phase 2 is
blocked on a connectivity decision that surfaced a real architectural constraint
(ADR-054 D3) — not a CLI bug. Resume here.

### Test VM — provisioned and working

- Host: `core-cli@192.168.20.46` (Proxmox container `CT103`), Ubuntu 24.04.3 LTS,
  Python 3.12.3, matches the "VM tech specs" section above.
- User `core-cli` created with NOPASSWD sudo (`/etc/sudoers.d/99-core-cli`).
- SSH access: key-based, public key
  `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFS+sNftHmmj0nvFtG6uYCCE9Zsf/boJQpbgqRVbj9eg claude-code-core-cli-smoke-test`
  is in `core-cli`'s `authorized_keys` on the VM. **The matching private key lives
  in this session's scratchpad directory and does not persist across sessions** —
  next session, either regenerate a keypair and re-authorize it on the VM (fast,
  the VM itself is otherwise fully prepped), or the governor can supply a durable
  key. Don't re-run `adduser`/sudoers/`.ssh` setup — that part is done.
- `scripts/core-cli-vm-prep.sh` ran clean on this VM (OS update + Python 3.12 +
  venv). No need to re-run.

### Phase 1 — PASS (run 2026-07-11/12 on the VM above)

- 1.1 `pip install core-cli`: exit 0, no dependency conflicts. Installed
  `core-cli-1.0.0` + `core-runtime-2.8.0`.
- 1.2 `core --help`: all 7 command groups present (`lane`, `proposals`, `secrets`,
  `code`, `symbols`, `vectors`, `project`).
- 1.3 `pip show core-cli`: `Version: 1.0.0`, `Requires: core-runtime`. Matches
  expected.

### Phase 2 — BLOCKED on CORE_API_URL target selection

P3 ("CORE instance reachable from VM") failed against the obvious target and
surfaced a real constraint, not a bug:

- **`192.168.20.22`** (the main CORE dev host, where `core-daemon`/`core-api`
  actually run) — connection refused. Root cause: `core-api` binds
  `127.0.0.1:8000` only, per **ADR-054 D3** ("no auth for Phase 1; loopback
  binding only" — deliberate, since the API has zero authentication.
  "No external exposure is sanctioned while this decision is in force."
  Promotion to non-loopback requires bearer-token auth + a dedicated ADR).
  Rebinding this instance to `0.0.0.0` to satisfy the smoke test would violate
  that ADR outright — not doing that without an explicit governor decision to
  amend/except ADR-054.
  - Proposed (not yet executed) ADR-054-compliant alternative: SSH reverse
    tunnel — `ssh -R 8000:localhost:8000` from the CORE host into the VM, so
    the VM's `localhost:8000` forwards over the authenticated SSH link to
    the loopback-bound `core-api`. Uvicorn's bind address never changes.
  - Governor redirected to try `.45` instead before deciding on the tunnel.

- **`192.168.20.45`** (Proxmox container `CT102`, root access) — checked and
  it's a dead end as-is: no `core-api`/`core-daemon` running, no matching
  systemd units, no Docker, no Postgres/Qdrant, no CORE git checkout (only an
  unrelated `/opt/myproject/.git`). What exists is a static venv at
  `/opt/core-proof` (dated 2026-06-29) with `core`/`core-admin` entry points —
  looks like a leftover "does the install work" check, not a live service.
  Spec: 2 vCPU / 4GiB RAM / 512MiB swap / 8GiB disk (ZFS), **6.6GB free**.

### Decision in progress — stand up core-daemon + core-api on `.45`

Governor chose this over the SSH tunnel to `.22`. Not started yet — this is a
full `coldroom-prep.sh`-style build from scratch (Docker install, pull
Postgres 16 + Qdrant images, clone CORE, configure `.env`, run migrations,
start services), scoped to a disposable test box rather than touching the
real dev instance. Two open risks flagged to the governor, neither resolved:

1. **Disk headroom is tight.** 6.6GB free has to cover Docker engine + two
   container images + a full CORE clone + a Python venv whose deps alone
   (numpy/scipy/scikit-learn/grpcio, per the Phase 1 install) ran several
   hundred MB. Real risk of running out mid-install. Option: grow the ZFS
   volume via Proxmox before starting, if easily available.
2. **ADR-054 D3 tension, again.** Even on a disposable box, binding an
   unauthenticated `core-api` to a non-loopback interface is the exact thing
   D3 says isn't sanctioned. Treating this as acceptable because the instance
   is disposable/test-only is a judgment call the governor made implicitly by
   redirecting here — flagging once more for the record, not blocking on it.

### Next steps (resume here)

1. Governor decision: grow `.45`'s disk first, or proceed at 6.6GB free?
2. If proceeding: install Docker + Compose on `.45`, pull `postgres:16` +
   `qdrant/qdrant:v1.9.0`, clone CORE, configure `.env`, run migrations, start
   `core-daemon`/`core-api` bound for LAN reachability.
3. Re-authorize an SSH key for `core-cli` on the `.46` VM (private key was
   session-scoped and is gone).
4. Set `CORE_API_URL` on the VM to point at `.45`, confirm P3 health check,
   resume Phase 2.1 (`core code actions`).

---

## Prerequisites (governor completes before handing over)

| # | Item | Expected state |
|---|------|---------------|
| P1 | Ubuntu 24.04 LTS VM, fresh | No Python packages pre-installed beyond OS baseline |
| P2 | Python 3.12 available | `python3.12 --version` returns `3.12.x` |
| P3 | CORE instance reachable from VM | `curl http://<CORE_HOST>:8000/health` → `{"status":"ok"}` |
| P4 | `CORE_API_URL` env var set | `export CORE_API_URL=http://<CORE_HOST>:8000` |
| P5 | SSH access granted to Claude Code | key-based, non-root user with `sudo` for package installs |
| P6 | Test git repo available | Any real Python repo (≥500 LOC) cloned somewhere on the VM |

### VM tech specs

Proven sufficient by the container this test was originally validated on
(Proxmox, unprivileged LXC, Ubuntu 24.04 LTS) — this is a pip-install-and-HTTP-client
workload, no local database or container runtime needed, so the footprint is small:

| Resource | Spec |
|---|---|
| vCPU | 2 |
| RAM | 4 GiB |
| Swap | 512 MiB |
| Disk | 8 GiB |
| Container type | Proxmox LXC, unprivileged (a full VM works too — LXC is the proven minimum) |
| OS | Ubuntu 24.04 LTS |

This is deliberately far lighter than `scripts/coldroom-prep.sh`'s cold-room VM
(which bakes in Docker + Postgres + Qdrant to run the full CORE stack for the
install-from-scratch demo, #562) — this test only installs a pip package and
talks to an already-running CORE instance over HTTP.

---

## Phase 1 — Install

### 1.1 Install from PyPI into a fresh venv

```bash
python3.12 -m venv ~/core-test-env
source ~/core-test-env/bin/activate
pip install core-cli
```

**Pass:** `pip install` exits 0, no dependency conflicts.

### 1.2 Verify entry point

```bash
core --help
```

**Pass:** Typer help text appears listing all command groups
(`code`, `lane`, `project`, `proposals`, `secrets`, `symbols`, `vectors`).

### 1.3 Verify version

```bash
pip show core-cli
```

**Pass:** `Version: 1.0.0`, `Requires: core-runtime`.

---

## Phase 2 — Connectivity

### 2.1 API reachability

```bash
core code actions
```

**Pass:** Rich table of registered Atomic Actions renders. At least one row present.

**Fail signal:** `Connection refused` or `CoreApiClient: failed to connect` → check
`CORE_API_URL` and that `core-api` is running on the CORE host.

### 2.2 Inspect bridges

```bash
core code bridges
```

**Pass:** Table of declared architecture bridge points. `available: true`.

### 2.3 Inspect bridges with filter

```bash
core code bridges --consuming AuditFinding
```

**Pass:** Subset of bridges, all with `AuditFinding` in `consuming_types`.

---

## Phase 3 — Read-only commands (no `--write`, no side effects)

Run each command and confirm it exits 0 with structured output. Note any unexpected
errors but do not stop the sequence — record and continue.

### 3.1 Code group

| Command | Expected output shape |
|---------|----------------------|
| `core code actions` | Table: action_id / category / impact / description |
| `core code bridges` | Table: bridge id / title / layers |
| `core code audit-duplicates` | Confirmation line or "scan complete" |
| `core code lint` | Lint findings or "clean" |
| `core code check-imports` | Import violations or "none found" |
| `core code check-ui` | Rich usage violations or "clean" |
| `core code integrity` | Integrity report |
| `core code logging` | Logger compliance report |

### 3.2 Symbols group

| Command | Expected output shape |
|---------|----------------------|
| `core symbols audit` | Symbol audit findings or "all present" |
| `core symbols sync` | Sync confirmation (dry-run default) |

### 3.3 Vectors group

| Command | Expected output shape |
|---------|----------------------|
| `core vectors status` | Vector store status (collection counts, last sync) |
| `core vectors query "atomic action"` | Nearest-neighbour results |

### 3.4 Proposals group

| Command | Expected output shape |
|---------|----------------------|
| `core proposals list` | Table of proposals or "none found" |

### 3.5 Lane group

| Command | Expected output shape |
|---------|----------------------|
| `core lane list` | Delegated findings or "empty" |

---

## Phase 4 — Write commands `[WRITE]`

Each step below requires explicit governor confirmation before execution. Claude Code
will describe the intended action and wait for "go ahead".

### 4.1 Format dry-run (safe — no actual write)

```bash
core code format
```

**Pass:** Run ID returned, poll completes, `status: completed`. No files changed.

### 4.2 `[WRITE]` Format apply

```bash
core code format --write
```

Governor confirms: "go ahead with format --write on the test repo."

**Pass:** Formatted files reported, run status `completed`.

### 4.3 Fix docstrings dry-run

```bash
core code fix-docstrings
```

**Pass:** Run kicked off, poll completes with findings count.

### 4.4 `[WRITE]` Fix imports

```bash
core code fix-imports --write
```

Governor confirms before execution.

**Pass:** Import ordering corrected, status `completed`.

---

## Phase 5 — BYOR onboarding flow `[WRITE]`

Uses the test git repo from P6. This is the primary external-adoption path.

### 5.1 Dry-run onboard

```bash
core project onboard /path/to/test-repo
```

**Pass:** Preview of files to be delivered printed. "DRY-RUN complete" footer. No
files written to the repo.

### 5.2 `[WRITE]` Staged onboard

```bash
core project onboard /path/to/test-repo --write --stage
```

Governor confirms before execution.

**Pass:** Output shows `Staged to work/staged/<name>/.intent`. Confirm staged files
exist on the CORE host.

### 5.3 Promote staged onboard `[WRITE]`

```bash
core project promote /path/to/test-repo
```

Governor confirms before execution.

**Pass:** `.intent/` directory created inside the test repo. Confirm with
`ls /path/to/test-repo/.intent/`.

### 5.4 Scout the onboarded repo

```bash
core project scout /path/to/test-repo
```

**Pass:** Scout findings returned (rules induced from the repo's codebase).

---

## Phase 6 — Secrets (if configured on CORE host)

```bash
core secrets list
```

**Pass:** Secret entries listed or "none configured". No crash.

> Skip this phase if the CORE instance has no secrets configured — note as
> "not applicable" rather than a failure.

---

## Pass / Fail criteria

| Grade | Condition |
|-------|-----------|
| **SHIP** | Phases 1–3 all pass; Phase 5.1 passes; no unhandled exceptions |
| **SHIP WITH NOTES** | 1–3 pass; one or two read commands return unexpected empty results attributable to CORE instance state (not a CLI bug) |
| **HOLD** | Any Phase 1–2 failure; entry point missing; `core-runtime` version mismatch; any unhandled exception not attributable to CORE instance config |

---

## What Claude Code records

For each command:
- Exit code
- First 10 lines of stdout / full stderr on non-zero exit
- Whether output matches expected shape above
- Any unexpected exceptions with full traceback

Final report: pass/fail per phase, overall grade, and any issues filed against
`core-cli` or `core-runtime`.
