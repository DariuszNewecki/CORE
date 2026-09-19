# Getting Started

## Two ways to use CORE

You don't need the full runtime to start. Pick the path that matches your goal:

| Goal | Path | What you need |
|------|------|---------------|
| **Govern your own repo** | `core project onboard <path> --write` (machinery floor), then `core project scout <path> --write` (fitted rules), then add the [GitHub Action](cold-reviewer.md) — walkthrough: [byor-quickstart.md](byor-quickstart.md) | `pip install core-cli` **and a running CORE API** (Postgres + Qdrant behind it) |
| **Add a rule pack to a repo that already has a `.intent/`** | `pip install core-runtime`, then `core-admin project adopt-pack core/starter-python --write` *inside that repo* | Python 3.12+ and a repo with a `.intent/` machinery floor |
| **Govern my repo in CI** | [GitHub Action](cold-reviewer.md) — runs the constitutional audit on every PR, no local install | A GitHub repo **with a `.intent/` constitution** |
| **Run an audit locally, no services** | `pip install core-runtime`, then `core-admin code audit --offline` *inside a repo that has a `.intent/`* | Python 3.12+ **and a repo with a `.intent/`** |
| **Run the full thesis** (encounter → audit → remediate → verify, the autonomous daemon) | The full local runtime below — run it on **CORE itself** | Postgres + Qdrant + an LLM resource |

> **Govern your own repo (BYOR) — honest shape of the path today.** Delivering a constitution *into* an existing repo is not a zero-infrastructure step. `project onboard` (machinery floor: schemas, taxonomies, enforcement config) and `project scout` (fitted rules — proposed via LLM, or a curated four-rule menu without one; you ratify each before delivery) are consumer commands in `core-cli`, which is a pure HTTP client (ADR-146 D2): it needs a reachable CORE API, and the API needs Postgres + Qdrant. There is currently no offline `onboard`. What *is* service-free, from a plain `pip install core-runtime`: `core-admin project adopt-pack` (add a ready-made rule pack to a repo that already carries a `.intent/`) and `core-admin code audit --offline` (enforce the rules, immediately).
>
> **Step-by-step walkthrough** (fresh machine → API → onboard → violation → fix → PASS): [byor-quickstart.md](byor-quickstart.md)

The rest of this page covers the **full local runtime**.

---

## Requirements

| Dependency | Version |
|------------|---------|
| Python | ≥ 3.12 |
| PostgreSQL | ≥ 14 |
| Qdrant | latest |
| Docker | for services |
| Poetry | for deps |

You will also need an LLM resource — local model server or external API, your choice. Configure it via `.env` (see `.env.example` for the shape).

---

## Installation

> **Upgrading an existing database?** Since 2.10.2 the upgrade path is supported and
> operator-run: see [Upgrading an existing CORE database](#upgrading-an-existing-core-database)
> below. CORE never migrates a database on its own; `install-core.sh` and every service start
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

### See CORE govern itself (opt-in)

When you want the guided proof, run the isolated demonstration explicitly. It
needs Docker but **no** LLM key, and runs entirely inside a disposable clone and
disposable, loopback-only Postgres + Qdrant — your checkout, git index, database,
and daemon are never touched:

```bash
poetry run core-admin demo consequence-chain
```

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

## Upgrading an existing CORE database

CORE never migrates a database on its own. `install-core.sh` and every service start (`core-admin
daemon start`, the API, the `core-engine` container) check the schema state **read-only** and refuse
to run against a database that is not current. Migration is a deliberate, operator-run step.

**Fresh 2.10.2 installation** — `./install-core.sh` (or `./install-core.sh --bare --db-url … --qdrant-url …`)
loads `schema.sql` into a database that has no CORE schema, in one transaction, and then shows
`core-admin database status` reporting the ledger current. Nothing else is needed. A failed load
leaves nothing behind (there is no drop-and-retry); the installer refuses and names `var/logs/schema-apply.log`.

**Before any upgrade** — stop CORE so nothing writes during migration, using the commands your
installation already has:

| Installation | Stop | Start again (only after `status` exits 0) |
|---|---|---|
| systemd units (`core-admin daemon up` installs) | `core-admin daemon down` | `core-admin daemon up` |
| bare (`install-core.sh --bare`) | `./stop.sh` | `./start.sh` |
| installer Docker path (API started by the installer, daemon by `make daemon-start`) | `make daemon-stop` and `make stop` | `./install-core.sh` (re-verifies status, starts the API) and `make daemon-start` |

Take your normal database backup. Then check what you have:

```bash
poetry run core-admin database status          # exit 0 current · 2 not current · 1 the check itself failed
```

**Upgrading a database created by v2.9.1** — `status` reports an empty ledger on a populated
schema and suggests baseline `v2.9.1`:

```bash
poetry run core-admin database migrate --adopt-baseline v2.9.1          # dry run: verifies the baseline's probes, records nothing
poetry run core-admin database migrate --adopt-baseline v2.9.1 --write  # records the ledger through v2.9.1
poetry run core-admin database migrate --write                          # applies the 14 pending migrations, one transaction each
poetry run core-admin database status                                   # must exit 0: current
```

**Upgrading a database created by v2.10.1** — `status` suggests baseline `v2.10.1`:

```bash
poetry run core-admin database migrate --adopt-baseline v2.10.1 --write
poetry run core-admin database migrate --write      # 1 applied, 4 reconciled: structure the schema already carries is recorded, not re-run
poetry run core-admin database status               # must exit 0
```

From an installed wheel (`pip install core-runtime`) the same commands work with only `DATABASE_URL`
set (the manifest, SQL and `schema.sql` ship inside the wheel); the `core-engine` container exposes
them as `status` and `migrate`.

**Already current** — `status` exits 0; `migrate --write` reports nothing pending; re-running the
installer continues. Nothing is changed.

**Pending migrations on a ledgered database** — `status` lists them; run `database migrate --write`,
then `status`.

**Contradiction** — `status` names a recorded migration whose verification probe fails: the ledger
claims a change the schema lacks. `migrate --write` refuses. Do not adopt a baseline over it and do
not hand-edit `core._migrations`; restore the database from backup, or report the status output.

**Unrecognised schema** — a `core` namespace that no declared baseline matches: `status` reports an
empty ledger with no matching baseline and the installer refuses. The database was not created by a
released CORE version. Nothing is changed; do not force a baseline.

**What a refusal means** — each migration runs together with its ledger row in one transaction
under a lock. A failure leaves that migration rolled back and unrecorded, earlier ones recorded, and
re-running `migrate --write` is safe once the cause is fixed (the message names it — for example a
`runtime_settings` key not yet recorded as migrated in `config_migration_log`). Concurrent
invocations apply each migration once. Governance history (`blackboard_entries`,
`autonomous_proposals`, `proposal_consequences`) is preserved: rows, identities, content and
relationships survive; a v2.9.1 upgrade updates `updated_at` on existing blackboard rows and turns
retired `draft` proposals `pending`, as those migrations declare.

**Restart only after `status` exits 0.** A service that starts is proof of a matching schema when
the database is reachable; one that refuses names the remedy in its log (daemon and `core-engine`
exit 78; the API's startup fails under uvicorn, exit 3).

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

CORE uses Qdrant for semantic search across constitutional documents and architectural papers. This is needed for the full (non-offline) audit and for context builds — skip it if you only ran `code audit --offline`. Sync the vector collections:

```bash
poetry run core-admin vectors sync --write
```

This indexes `.intent/` governance documents and `.specs/` architectural papers into searchable vector collections. Context builds draw evidence from these collections.

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
poetry run core-admin workers blackboard --filter "audit.violation"  # live findings
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
