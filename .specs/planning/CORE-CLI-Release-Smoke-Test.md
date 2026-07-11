# core-cli 1.0.0 — Release Smoke Test

**Purpose:** End-to-end validation of `core-cli 1.0.0` on a vanilla Ubuntu VM against a
running CORE instance. Executed by Claude Code with direct VM access. The governor's job
is to hand over SSH access and approve any `--write` steps explicitly.

**Scope:** install → connect → read commands → write commands → BYOR flow.
Write-destructive steps are marked `[WRITE]` and require explicit governor confirmation
before execution.

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
