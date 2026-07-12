# CORE Clean-Room Rebuild & Test Runbook

**Goal:** rebuild the test estate from zero to validate the *complete* installation
procedures (both the full CORE runtime and the `core-cli` consumer) from documented
settings only — proving reproducibility and catching any drift/doc gaps. End state: two
fresh VMs plus a reusable Proxmox template.

**Decided topology (2026-07-12):**
- **VM-1 — CORE runtime host** (full stack, source install, → Proxmox template).
- **VM-2 — `core-cli` consumer** (pip install, points at VM-1's API over the LAN).

This retires the ADR-054 tunnel to the dev box (`.22`) and gives a co-located host where
BYOR `promote`/`scout` writes actually work (finding F-1).

**Division of labor:**
- **Governor (Proxmox / out-of-band):** destroy old containers; create fresh VMs; install
  `openssh-server`; authorize the SSH key; hand over IPs + specs; snapshot VM-1 → template.
- **Claude (over SSH):** run all software provisioning scripts, configure, start services,
  run the test matrix, report. Writes an execution log back into this doc.

---

## Note: no JWT / secrets step needed

Current OSS CORE (v2.9.0) has **no auth guard** — the JWT/UAC fields were extracted to
core-platform (`dab0187c`). `install-core.sh` creates `.env` from `.env.example` with
demo-ready defaults (only `DATABASE_URL` + `QDRANT_URL` are sed-injected; an LLM key is
*optional*, needed only for autonomous code-gen). So a fresh install boots with no secret
provisioning. Do **not** copy the dev box's `.env` (it carries stale, now-unused fields).

---

## VM specs

| | VM-1 (runtime host) | VM-2 (consumer) |
|---|---|---|
| Role | Full CORE stack: Docker + Postgres 16 + Qdrant + CORE | pip `core-cli` HTTP client |
| vCPU | 4 (audit/vectorize is CPU-heavy) | 2 |
| RAM | 8 GiB | 4 GiB |
| Swap | 2 GiB | 512 MiB |
| Disk | **30 GiB** (Docker + 2 images + poetry venv w/ numpy/scipy + repo) | 8 GiB |
| OS | Ubuntu 24.04 LTS | Ubuntu 24.04 LTS |
| Container | Proxmox VM or unprivileged LXC (LXC needs Docker-in-LXC nesting enabled) | Unprivileged LXC (proven) |

> VM-1 disk is the risk knob — the abandoned `.45` attempt had only 6.6 GB free and was
> too tight. 30 GiB gives comfortable headroom.

---

## Phase 0 — Teardown (governor)

Destroy the current test containers (settings are documented here + in
`CORE-CLI-Release-Smoke-Test.md`). Nothing on them needs preserving — the persistent SSH
key lives on the dev box at `~/.ssh/core_cli_smoke`, and both prep recipes are in-repo.

- Old core-cli test VM: `.46` (CT103).
- Any leftover full-stack attempt: `.45` (CT102, the stale `/opt/core-proof`).

---

## Phase 1 — VM-1: CORE runtime host

**Governor:** create the VM (specs above), `apt install openssh-server`, authorize the key
`~/.ssh/core_cli_smoke.pub` for a sudo user, hand over the IP. For LXC, enable Docker
nesting (`features: nesting=1,keyctl=1`).

**Claude (over SSH):**
1. `scripts/coldroom-prep.sh` — Docker (official repo) + pre-pull `postgres:16` +
   `qdrant/qdrant:v1.9.0` + Poetry. (Run its documented pre-steps first if not baked in.)
2. `git clone https://github.com/DariuszNewecki/CORE.git && cd CORE`
3. `./install-core.sh` — `docker compose up` (PG + Qdrant), `poetry install` (**editable**,
   in-project venv — this is what avoids the shadow-wheel trap), `.env` from `.env.example`,
   run migrations, start `core-daemon` + `core-api` (loopback:8000).
4. **Verify:** `curl http://127.0.0.1:8000/health` → `{"status":"ok"}`; `core-admin`
   available; `import shared` resolves to the repo `src/`, not site-packages (the drift
   check); a few read commands render.
5. Decide LAN reachability for VM-2: since OSS CORE is auth-free, either bind `core-api` to
   the LAN on this **disposable** box, or reverse-tunnel from VM-2. (Disposable test box →
   LAN bind is acceptable here; document the choice.)

**Governor:** once VM-1 is verified clean, shut down → snapshot → convert to **Proxmox
template**; future clean tests are a linked-clone away.

---

## Phase 2 — VM-2: `core-cli` consumer

**Governor:** create the VM (specs above), `openssh-server`, authorize the key, hand over IP.

**Claude (over SSH):**
1. `scripts/core-cli-vm-prep.sh` — OS update + Python 3.12 + venv.
2. `python3.12 -m venv ~/core-env && source ~/core-env/bin/activate && pip install core-cli`
   → pulls `core-cli 1.0.1` + `core-runtime 2.9.0` (the pinned pair).
3. `export CORE_API_URL=http://<VM-1-IP>:8000`
4. **Verify:** `core --help`, `pip show core-cli` (1.0.1, requires core-runtime>=2.9.0),
   health via `core code actions`.

---

## Phase 3 — Test matrix

| Test | Where | What it proves |
|---|---|---|
| Full-stack install from zero | VM-1 | `install-core.sh` works end-to-end from public docs (#561/#562); no hidden manual steps |
| Consumer read path | VM-2 → VM-1 | `core code/symbols/vectors/proposals/lane` against a clean non-dev instance (the Phase 1–3 smoke suite) |
| Co-located BYOR writes | on VM-1 | `onboard --write --stage` → `promote` → `scout` into a **local** repo (the path F-1 showed needs co-location) |
| Pinned pair | both | `core-cli 1.0.2` + `core-runtime 2.9.1` resolve and interoperate cleanly |
| `code --write` (optional) | VM-1 | `format/format-imports --write` against a throwaway `REPO_PATH` (follow-up #2) |

---

## Rebuild-completeness checklist (watch for doc gaps)

Treat any step the recipes *don't* cover as a documentation defect to fix, not a one-off:
- [x] `coldroom-prep.sh` pre-steps (openssh, key auth) are stated but not scripted —
  confirmed still true 2026-07-12; now documented for operators in
  `CORE-CLI-VM-Test-Access-Runbook.md` (written after burning time on this exact gap).
- [ ] LXC Docker-nesting requirement (if using LXC) — Docker ran fine on `.48` (an
  unprivileged LXC) without me requesting any nesting change; unclear whether nesting
  was already enabled at the Proxmox host level or genuinely wasn't needed. Not
  conclusively answered.
- [ ] `install-core.sh` runs clean with zero interactive prompts on a truly fresh box —
  **not tested**; `.48`'s setup was done piecewise (`poetry install`, `docker compose
  up`, manual schema apply, manual `uvicorn`), not via `install-core.sh` itself. Also
  found and fixed two real `coldroom-prep.sh` bugs in the process (stale
  `QDRANT_IMAGE` pin, missing `python3-pip`/`python3-venv`) — the script `.48` should
  have used but didn't.
- [x] `.env.example` defaults are sufficient for a non-LLM install — confirmed 2026-07-12:
  `DATABASE_URL`/`QDRANT_URL` defaults matched `docker-compose.yml` with zero edits;
  full BYOR walkthrough (including Scout's offline 4-rule fallback) passed with no LLM
  configured.
- [ ] LAN-reachability choice for an auth-free instance is documented (bind vs tunnel) —
  not exercised; only the same-host (VM-1-equivalent) path was tested, no VM-2.

---

## Execution log

_(Claude appends dated results here as phases run.)_

- **2026-07-12.** Phase 0 (teardown) + Phase 1 (VM-1) effectively completed, though not
  via the documented script path — see the checklist note above. Container `.48`
  (hostname `core-runtime`, Ubuntu 24.04 LXC) stood up with the full stack (Docker +
  Postgres 16 + Qdrant v1.18.0 + Poetry + `core-api` from source) and separately
  `core-cli` installed fresh from PyPI into its own venv on the same host. The
  "Co-located BYOR writes" test matrix row passed: full onboard → scout → audit
  PASS/FAIL/PASS walkthrough, all green. VM access procedure written up as
  `CORE-CLI-VM-Test-Access-Runbook.md`. All services stopped and containers removed
  afterward (`docker compose down` + kill `uvicorn`) — `.48` is idle, not destroyed.
  **Not done:** Phase 2 (VM-2 consumer, LAN-separated read-path testing) and the
  Proxmox-template snapshot step.
