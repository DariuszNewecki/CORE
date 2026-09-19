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

> ⚠️ **Upgrading an existing database to v2.10.1 is currently unsupported.** A *clean* v2.10.1
> installation is not the affected scenario. Re-running `./install-core.sh` on an existing
> installation does **not** migrate the schema — it skips schema work when tables already exist.
> `core-admin database migrate` without a mutation flag is inspection/dry-run only. Do **not** run
> `core-admin database migrate --bootstrap` after switching an existing database to a newer
> checkout: it can mark migrations as applied without executing them. CORE may start against a
> stale schema and then fail during API and daemon work, so a successful startup is not proof
> of a successful upgrade. Do not attempt the upgrade until the corrected release and its
> supported procedure are available (ADR-162, G11).
>
> On `main` (unreleased) the migration commands have already changed — `--write` replaces
> `--apply`, `--bootstrap` is gone, `--adopt-baseline <tag>` verifies a baseline before
> recording it, and `database status` reports contradictions read-only. See
> [`docs/cli-reference.md`](cli-reference.md#database--postgresql-state-management). On `main`
> the API and the daemon also **refuse to start** against a schema the code does not match
> (pending migrations, an unledgered schema, or a ledger/schema contradiction): the daemon and
> the `core-engine` container exit **78** and the log names the exact remedy
> (`core-admin database migrate --write`, or `--adopt-baseline <tag> --write` first); the API's
> startup fails under uvicorn (exit 3, uvicorn's own contract) with the same message. A successful start is therefore proof of a
> matching schema — but the warning above stands until the release that completes ADR-162.

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

## Start the Services

CORE requires PostgreSQL and Qdrant running before any commands execute. The
bundled `docker-compose.yml` provides both:

```bash
# Start Postgres + Qdrant
docker compose up -d
```

Create the schema in the fresh `core` database. `schema.sql` at the repository root is
the canonical schema for a **fresh** install. (A migration ledger — `infra/migrations/manifest.yaml`
+ `core._migrations` — exists for existing databases, but the upgrade path is currently
unsupported; see the warning above.)

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
