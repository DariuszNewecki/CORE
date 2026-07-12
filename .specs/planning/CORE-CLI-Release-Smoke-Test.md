# core-cli 1.0.0 — Release Smoke Test

**Purpose:** End-to-end validation of `core-cli 1.0.0` on a vanilla Ubuntu VM against a
running CORE instance. Executed by Claude Code with direct VM access. The governor's job
is to hand over SSH access and approve any `--write` steps explicitly.

**Scope:** install → connect → read commands → write commands → BYOR flow.
Write-destructive steps are marked `[WRITE]` and require explicit governor confirmation
before execution.

---

## Run log

**Status as of 2026-07-12: COMPLETE — grade SHIP (after fix).** Connectivity was
resolved via an ADR-054 D3-compliant SSH reverse tunnel (the `core-api` bind address
never changed). The first end-to-end run graded **HOLD** — the published
`core-runtime 2.8.0` wheel was stale relative to what `core-cli 1.0.0` requires. Two
fixes were applied and verified: (1) `core-runtime` bumped to **2.9.0** and re-published
to PyPI; (2) a drifted dev `.venv` (a stray 2.8.0 wheel shadowing the editable `src/`)
was repaired. A full re-run then passed **every** command → **SHIP**. See "Outcome".

**This grade is now superseded** — later the same day, `core-runtime 2.9.1` and
`core-cli 1.0.2` shipped with further fixes (F-1/F-2 closed, F-4 found+fixed) and a
full same-host BYOR walkthrough passed on a fresh VM. See the "Update 2026-07-12
(later same day)" note under "Findings" below, and
`CORE-CLI-2.9.0-Followups.md` for the canonical current state.

### Test VM — provisioned and working

- Host: `core-cli@192.168.20.46` (Proxmox container `CT103`), Ubuntu 24.04.3 LTS,
  Python 3.12.3, matches the "VM tech specs" section above.
- User `core-cli` created with NOPASSWD sudo (`/etc/sudoers.d/99-core-cli`).
- SSH access: key-based. A **persistent** keypair now lives on the CORE dev host
  `.22` at `~/.ssh/core_cli_smoke` (public key comment
  `claude-code-core-cli-smoke-test-persistent`); its public key is authorized for
  `core-cli` on the VM. This survives across sessions — no need to regenerate.
  Don't re-run `adduser`/sudoers/`.ssh` setup — that part is done.
- `scripts/core-cli-vm-prep.sh` ran clean on this VM (OS update + Python 3.12 +
  venv). No need to re-run.

### Phase 1 — PASS (run 2026-07-11/12 on the VM above)

- 1.1 `pip install core-cli`: exit 0, no dependency conflicts. Installed
  `core-cli-1.0.0` + `core-runtime-2.8.0`.
- 1.2 `core --help`: all 7 command groups present (`lane`, `proposals`, `secrets`,
  `code`, `symbols`, `vectors`, `project`).
- 1.3 `pip show core-cli`: `Version: 1.0.0`, `Requires: core-runtime`. Matches
  expected.

### Connectivity — resolved via ADR-054 D3-compliant reverse tunnel

The earlier block (bind `127.0.0.1:8000` only, per **ADR-054 D3**) was resolved
without touching the `core-api` bind address. From the CORE dev host `.22`:

```
ssh -R 8000:localhost:8000 core-cli@192.168.20.46
```

The VM's `localhost:8000` now forwards over the authenticated SSH link to the
loopback-bound `core-api` on `.22`. Uvicorn's bind address never changed →
fully ADR-054 D3 compliant. P3 health check through the tunnel returned
`{"status":"ok"}`. The abandoned "stand up a full stack on `.45`" plan was
dropped in favour of this (lighter, ADR-clean, uses the live instance).

### Phase 2–6 results (run 2026-07-12 over the tunnel)

`CORE_API_URL=http://localhost:8000` on the VM. All commands invoked from the
installed `core-cli 1.0.0` venv.

Column "2.8.0" = first run (published stale wheel). "2.9.0" = re-run after the
republish + venv repair.

| Phase | Command | 2.8.0 | 2.9.0 |
|---|---|---|---|
| 2.1 | `core code actions` | ✅ table | ✅ |
| 2.2 / 2.3 | `core code bridges [--consuming]` | ❌ no `analysis_bridges` | ✅ Architecture Bridges table |
| 3.1 | `core code audit-duplicates` | ✅ scan complete | ✅ |
| 3.1 | `core code lint` / `check-imports` / `check-ui` | ✅ (exit 1 = findings, no traceback) | ✅ |
| 3.1 | `core code logging` | ✅ | ✅ |
| 3.1 | `core code integrity` | ⚠️ no such command (doc drift) | ⚠️ n/a |
| 3.2 | `core symbols sync` | ✅ dispatched `sync.db` | ✅ |
| 3.2 | `core symbols audit` | ❌ no `symbols` | ✅ 2749 symbols pending |
| 3.3 | `core vectors status` / `query` | ❌ no `vectors` | ✅ Qdrant collections |
| 3.4 | `core proposals list` | ✅ | ✅ |
| 3.5 | `core lane list` | ✅ 13 findings | ✅ |
| 4 | `core code format` / `format-imports` / `docstrings` (dry-run) | ✅ | ✅ |
| 5.1 | `core project onboard <repo>` (dry-run) | ❌ no `project` (BYOR broken) | ✅ DRY-RUN complete |
| 6 | `core secrets list` | ❌ no `secrets` | ✅ Encrypted Secrets table |

### Outcome — HOLD on first run, SHIP after fix

**Root cause of the HOLD: `core-cli 1.0.0` was published against an unreleased
`core-runtime` API surface.** CORE source `src/api/cli/client.py` builds a
`CoreApiClient` with 17 sub-clients (incl. `symbols`, `vectors`, `secrets`,
`project`) and an `InspectClient` with `analysis_bridges`. The published
`core-runtime 2.8.0` wheel carried only a handful — `pyproject.toml` was never
bumped past `2.8.0` after this session's `api/cli/` additions. Every CLI command
routing through a missing sub-client raised `AttributeError`.

**Fix 1 — republish (done).** Bumped `core-runtime` `2.8.0 → 2.9.0`, tagged
`v2.9.0`, published to PyPI via OIDC Trusted Publisher. A fresh
`pip install core-cli` on the VM then pulled `core-runtime 2.9.0`, and
`symbols audit` / `vectors status` / `secrets list` / `project onboard` all
started working. (Note: an *in-place* `pip install --upgrade core-runtime` from
2.8.0→2.9.0 deletes the shared `bin/core` script — 2.8.0 wrongly shipped a `core`
entry point that 2.9.0 correctly dropped per ADR-146 D6. A fresh install is
clean; this is only an upgrade-path artifact.)

**Fix 2 — dev `.venv` repair (done).** `bridges` still 404'd after the republish
because the running `core-api` (21h uptime) predated the `/v1/analysis/bridges`
route. Restarting it exposed a deeper problem: **a stray `core-runtime 2.8.0`
wheel had been pip-installed into the dev `.venv` on 2026-07-11 14:31, planting
copies of `api/body/mind/will/shared/cli` that shadowed the editable `src/`**
(`core.pth → /opt/dev/CORE/src`). The daemon had been running the stale wheel,
not `src/`, and the wheel lacked recent fixes (the `governance_pack` rule-index
skip), so a restart failed with `Duplicate rule_id detected: starter.no_bare_except`.
Repaired with `pip install -e .` in the dev `.venv` — uninstalls the wheel,
un-shadows `src/`, regenerates the `core-admin` entry point. `core-api` +
`core-daemon` restarted clean on current `src/`; `/v1/analysis/bridges` now
serves HTTP 200 and `core code bridges` renders the table.

**Follow-ups:**

1. ✅ Done — `core-cli 1.0.1` pins `core-runtime>=2.9.0` (published).
2. ✅ Done — command drift fixed in this doc (`code integrity` removed; Phase 4 uses
   `docstrings` / `format-imports`; Phase 4 scope warning added).
3. See "Phase 5 write-flow exercise" below — BYOR `[WRITE]` apply steps now run.

### Phase 5 write-flow exercise (run 2026-07-12, core-cli 1.0.1 + core-runtime 2.9.0)

The `[WRITE]`-apply steps were exercised. Results and findings:

- **`onboard --write --stage`** → ✅ staged a full standard Phase-A machinery floor
  (constitution + enforcement + taxonomies + META, 29 files) to
  `work/staged/<basename>/.intent` **on the API host**. Does not read the source
  repo — the floor is a fixed template keyed by the repo basename.
- **`promote`** → ✅ writes `.intent/` into the target repo — **but only when the
  target path exists on the API host.** Co-located run (repo on the API host):
  `.intent/` delivered cleanly. Cross-host run (repo on the remote CLI host, path
  absent on the API host): `API error 500: [Errno 13] Permission denied` — the API
  operates on its *own* filesystem, so a remote CLI's local repo path is
  meaningless to it.
- **`scout --write`** → ✅ induced a real rule from the repo (0% return-annotation
  coverage → an `ast_gate type_annotations` reporting rule). Ratification is
  **interactive by design** (`Action [a/r/c]`, no `--accept-all` per Scout D5), so a
  non-interactive/SSH run reviews nothing and writes nothing.

**Findings (candidates for follow-up, do not block SHIP):**

- **F-1 (topology):** BYOR `project onboard/promote/scout` are **API-host-filesystem
  operations**. The remote-CLI → central-API topology used for this smoke test does
  **not** support BYOR writes into a repo that lives only on the CLI host. The real
  adoption model is co-located (adopter installs CORE and points it at a local
  repo). The CLI's "pure HTTP client" framing holds for read/analysis commands but
  not for `project` writes, which assume shared filesystem locality.
- **F-2 (error handling):** cross-host `promote` leaks a raw `OSError` as
  `API error 500: [Errno 13] Permission denied: '<path>'`. Should be a clean 4xx
  ("target path not accessible on the CORE host") instead of a 500.
- **F-3 (automation):** `scout` cannot be run non-interactively (no batch-accept).
  Fine for a human operator; blocks CI/automated onboarding of induced rules. **Still
  open** as of 2026-07-12.

Only Phase 4 `code format/format-imports --write` remain un-exercised — deliberately,
since they mutate the CORE **instance's own** repo (see the Phase 4 scope warning),
not a throwaway target.

**Update 2026-07-12 (later same day) — F-1/F-2 closed, F-4 found and fixed, full
same-host walkthrough verified.** This doc's findings above are a snapshot from the
Phase 5 exercise; the live trail since then is tracked in
`CORE-CLI-2.9.0-Followups.md` (canonical, keep reading there — not duplicated here):

- F-1 closed as documented co-location (not built around) — `core-runtime 2.9.1`.
- F-2's first fix pass was incomplete; a second bug (`typer.Exit` isn't `SystemExit`
  in Typer 0.16.1) was found live and fixed — `core-runtime 2.9.1`.
- F-4 (new): relative paths (`.`) resolve against whichever process receives them,
  not the caller's shell — found live, fixed in `core-cli 1.0.2`.
- A full BYOR walkthrough (onboard → scout → audit PASS/FAIL/PASS) ran successfully
  end-to-end on a genuinely fresh VM with `core-cli 1.0.2` + `core-runtime 2.9.1`,
  both installed fresh from PyPI, `core-api` running from source on the same host.
  VM access procedure: `CORE-CLI-VM-Test-Access-Runbook.md`.
- The test VM referenced throughout this doc (`.46`, CT103) no longer exists — the
  container slot was rebuilt and repurposed as `.48` (`core-runtime` hostname) for
  the same-host test above, per `CORE-Cleanroom-Rebuild-Runbook.md`'s decided
  topology. Do not attempt to reach `.46`.

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
| `core code logging` | Logger compliance report |

> Note: `core code` commands operate on the **CORE instance's own governed repo**
> (its configured `REPO_PATH`), not a user-supplied path. Against a dev instance
> that is `/opt/dev/CORE` itself. There is no `core code integrity` command.

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

> **Scope warning.** `core code format --write` / `format-imports --write` have **no
> repo argument** — they mutate the CORE instance's **own** governed repo
> (`REPO_PATH`), which on a dev instance is `/opt/dev/CORE` itself, not a throwaway
> test repo. Running `--write` there creates uncommitted changes in the live source
> tree that the autonomous daemon may scoop into a `fix.*` commit. Only exercise the
> Phase 4 `--write` steps against an instance whose repo you are willing to mutate,
> or point a disposable CORE instance at a throwaway `REPO_PATH`. The isolated
> external-adoption writes are Phase 5 (`core project *`, which DO take a repo path).

### 4.1 Format dry-run (safe — no actual write)

```bash
core code format
```

**Pass:** Run ID returned, poll completes, `status: completed`. No files changed.

### 4.2 `[WRITE]` Format apply (mutates the instance's own repo)

```bash
core code format --write
```

Governor confirms: "go ahead with format --write on this instance's repo."

**Pass:** Formatted files reported, run status `completed`.

### 4.3 Docstrings dry-run

```bash
core code docstrings
```

**Pass:** Run kicked off, poll completes with findings count.

### 4.4 `[WRITE]` Fix imports (mutates the instance's own repo)

```bash
core code format-imports --write
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
