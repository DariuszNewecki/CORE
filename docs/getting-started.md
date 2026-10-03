# Run the Full Runtime

This page installs and runs the **full CORE runtime** from a clone: PostgreSQL, Qdrant,
the API and the autonomous daemon. It is the path for running the whole thesis —
encounter → audit → remediate → verify — and the prerequisite for
[governing your own repository](byor-quickstart.md) and [GRC gap analysis](grc-gap-analysis.md).

If you only want to audit code against rules, you need none of it: see
[Start a governed project](start-a-project.md), which needs only Python.

## Requirements

| Requirement | Version / state |
|-------------|-----------------|
| Python      | **3.12+** — hard floor, checked by the installer |
| Docker      | Docker Engine with **Compose v2**, daemon **running** and reachable by your user |
| Poetry      | installed and on `PATH` |
| PostgreSQL  | ≥ 14 — provided by Docker on the default path |
| Qdrant      | latest — provided by Docker on the default path |

**No LLM is needed** to install CORE, run the offline audit, or run the consequence-chain
demo. An LLM (local model server or external API, your choice) is needed only for
autonomous code and test generation. Configure it in `.env` when you want that (see
`.env.example` for the shape).

### Prerequisites on a fresh Ubuntu 24.04

A fresh VM has none of the above except Python. One command per prerequisite, each
followed by the same check `install-core.sh` performs:

```bash
# Python 3.12+ (Ubuntu 24.04 ships 3.12)
python3 --version

# git, to clone CORE
sudo apt-get update && sudo apt-get install -y git

# Docker Engine + Compose v2, daemon running
sudo apt-get install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
docker compose version

# Let your user reach the Docker daemon, then start a NEW login session
# (log out and back in; `newgrp docker` works for the current shell only)
sudo usermod -aG docker "$USER"
docker info

# Poetry, on PATH
sudo apt-get install -y pipx
pipx install poetry
pipx ensurepath   # edits your shell rc files: open a new terminal afterwards
poetry --version
```

`pipx ensurepath` only takes effect in new shells. In a non-login or scripted shell, add
`export PATH="$HOME/.local/bin:$PATH"` before running the installer. These are the commands
a blank observer used on a fresh Ubuntu 24.04 VM in the 2026-09-20 newcomer test (#913).
Other distributions: follow [Docker Engine](https://docs.docker.com/engine/install/) and
[Poetry](https://python-poetry.org/docs/#installation), then run the same checks.

---

## Installation

> **Upgrading an existing database?** Since 2.10.2 the upgrade path is supported and
> operator-run: see [Upgrade a CORE database](upgrading.md). CORE never migrates a database on its own; `install-core.sh` and every service start
> check the schema state read-only and refuse to run against a database that is not current.

**One command** (recommended). Clone, then run the installer — it checks
prerequisites, installs dependencies, starts the services, applies the schema,
and finishes by **offering** the opt-in consequence-chain demo (it never runs
it for you):

```bash
git clone https://github.com/DariuszNewecki/CORE.git
cd CORE
./install-core.sh
```

If that succeeds you can skip to [Key Commands](#key-commands) — CORE is running.
The rest of this section is the same path, done by hand.

**What a healthy fresh install looks like.** The installer's offline audit ends with
`verdict DEGRADED`, not PASS: a few blocking rules need the running knowledge graph
or database and cannot be evaluated offline. The installer says so and continues;
that is expected. Without an LLM configured you will also see one line saying no LLM
is configured and that LLM-checked rules use a stub. That is the documented no-key
path, not a fault: an LLM is needed only for autonomous code generation. To see
CORE's internal start-up detail on any command, set `LOG_LEVEL=DEBUG`.

### See CORE govern itself (opt-in)

When you want the guided proof, run the isolated demonstration explicitly. It
needs Docker but **no** LLM key, and runs entirely inside a disposable clone and
disposable, loopback-only Postgres + Qdrant — your checkout, git index, database,
and daemon are never touched:

```bash
poetry run core-admin demo consequence-chain
```

It asks for one confirmation before it creates anything. In a non-interactive shell
(CI, `ssh host cmd`, an agent-driven terminal) add `--simulate-confirmation`; the
report records the confirmation as simulated.

In one run it seeds a real `linkage.assign_ids` violation, lets the real sensor,
remediator, proposal route, and executor find → propose → auto-approve (as
*policy-safe*, not "human approved") → fix → verify it, then prints the exact
recorded chain and re-audits clean. It **fails closed**: every link is asserted
and any missing one exits non-zero. See the [`demo`](cli-reference.md) command
reference for options (`--output`, `--keep-workspace`, `--simulate-confirmation`,
`--timeout-seconds`), exit codes, and cleanup.

### Manual installation

```bash
git clone https://github.com/DariuszNewecki/CORE.git
cd CORE
poetry install

cp .env.example .env
# Edit .env: set DATABASE_URL / QDRANT_URL if they differ from the defaults,
# and configure your LLM provider (see the LLM section of .env.example).
```

---

## Start the Services

CORE requires PostgreSQL and Qdrant running before any commands execute. The
bundled `docker-compose.yml` provides both:

```bash
# Start Postgres + Qdrant
docker compose up -d
```

Create the schema in the fresh `core` database. `schema.sql` at the repository root is
the canonical schema for a **fresh** install. (A migration ledger — `infra/migrations/manifest.yaml`
+ `core._migrations` — the migration ledger; a fresh `schema.sql` load seeds it completely, and
an upgraded database reaches the same ledger through the procedure below.)

```bash
# Apply the canonical schema to the empty database (runs psql inside the container,
# so you don't need a psql client on the host)
docker compose exec -T postgres psql -U postgres -d core < schema.sql
```

Verify the connection:

```bash
poetry run core-admin database status
```

---

## Your First Audit

Once installed, run a constitutional audit to see the current state of the codebase. Start with the **offline** audit — it needs no running services:

```bash
poetry run core-admin code audit --offline
```

Offline mode skips `knowledge_gate` and `llm_gate` (they require the knowledge
graph and an LLM provider) and reports the skip. Once `core-api` is running
(`./install-core.sh` starts it for you; or run it directly with `make run`), the
full audit runs every engine:

```bash
poetry run core-admin code audit
```

This runs the full constitutional rule library across all enforcement engines and reports:

- **Blocking violations** — must be resolved before autonomous operation
- **Warnings** — tracked but non-blocking
- **Advisory findings** — informational

A clean audit (zero blocking violations) is the precondition for autonomous operation.

---

## Sync the Vector Layer

CORE uses Qdrant for semantic search across constitutional documents and architectural papers. This is needed for the full (non-offline) audit and for context builds — skip it if you only ran `code audit --offline`. Populate the vector collections (on a fresh install they are empty; this asks for confirmation — add `--yes` to skip the prompt):

```bash
poetry run core-admin vectors rebuild --write
```

This embeds the code and tests and indexes `.intent/` governance documents and `.specs/` architectural papers into searchable vector collections. Context builds draw evidence from these collections.

---

## Key Commands

Apply structural fixes and sync state after code changes — `dev sync` first
fixes metadata (symbol IDs, headers, formatting), then syncs the knowledge graph
and vectors:

```bash
poetry run core-admin dev sync --write
```

Check the governor dashboard — five-panel situational awareness:

```bash
poetry run core-admin runtime dashboard
```

Check infrastructure health:

```bash
poetry run core-admin admin status
```

View governance coverage:

```bash
poetry run core-admin constitution status
```

---

## Understanding the Output

CORE's audit output is structured by policy domain. Each finding references:

- The rule that fired
- The file and line where the violation occurred
- The enforcement engine that detected it
- The enforcement strength (Blocking / Reporting / Advisory)

Blocking violations halt autonomous execution. They must be resolved — either by fixing the violation or by amending the constitution through the governed proposal process.

> **CLI severity tokens.** When filtering the audit by severity (`code audit --severity <level>`), the accepted values are `info`, `low`, `medium`, `high`, `block`. The threshold for blocking rules is the lowercase token `block` — not `blocking`.

---

## Going Further

### Turn on autonomy

So far you've driven CORE by hand. Start the daemon and it runs continuously —
finding violations, proposing fixes, and (for risk-classified-safe changes)
executing them, all coordinated on the blackboard:

```bash
make daemon-start            # background daemon (works on a fresh clone)
```

(If you've installed CORE's systemd user units, `core-admin daemon up` starts the
full set — `core-daemon`, `core-api`, and the worker instances — instead.)

With the daemon running, routine maintenance is **automatic**: `DbSyncWorker`
keeps the knowledge graph and vectors in sync on a ~5-minute cadence, and the
remediation loop proposes fixes for structural violations. You rarely need to
run `dev sync --write` by hand — that command is the synchronous *do-it-now*
version of what the daemon does continuously (useful when the tree isn't clean
yet, or the daemon is stalled).

Observe it working:

```bash
poetry run core-admin runtime dashboard                              # five-panel situational awareness
poetry run core-admin workers show --filter "audit.violation"       # live findings
```

### Let CORE write code (needs an LLM)

The deterministic fixers (symbol IDs, formatting) need no model. To have CORE
*generate* code — natural-language tasks and LLM-driven remediation — configure
an LLM provider in `.env` (see the LLM section), then run the remediation
pipeline for a rule:

```bash
poetry run core-admin workers remediate <rule>            # sensor → LLM proposes fix → canary → blackboard (review)
poetry run core-admin workers remediate <rule> --write    # ... and apply + commit the fix
```

This is governed generation under the same constitutional loop — the A2/A3
capability on the [Autonomy Ladder](autonomy-ladder.md).

---

## Next Steps

- [How It Works](how-it-works.md) — understand the constitutional model before making changes
- [CLI Reference](cli-reference.md) — full command reference
- [Contributing](contributing.md) — if you want to engage with the project
