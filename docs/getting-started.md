# Getting Started

## Two ways to use CORE

You don't need the full runtime to start. Pick the path that matches your goal:

| Goal | Path | What you need |
|------|------|---------------|
| **Govern your own repo** | `core-admin project onboard <path> --write` (machinery floor), then `core-admin project scout <path> --write` (fitted rules), then add the [GitHub Action](cold-reviewer.md) | Python 3.12+ and `pip install core-runtime` |
| **Govern my repo in CI** | [GitHub Action](cold-reviewer.md) — runs the constitutional audit on every PR, no local install | A GitHub repo **with a `.intent/` constitution** (scaffold one with `project onboard` + `project scout`) |
| **Run an audit locally, no services** | `pip install core-runtime`, then `core-admin code audit --offline` *inside a repo that has a `.intent/`* | Python 3.12+ **and a repo with a `.intent/`** |
| **Run the full thesis** (encounter → audit → remediate → verify, the autonomous daemon) | The full local runtime below — run it on **CORE itself** | Postgres + Qdrant + an LLM resource |

> **Govern your own repo (BYOR).** Two steps: (1) `core-admin project onboard <path> --write` delivers the machinery floor (schemas, taxonomies, enforcement config) into your repo — no LLM needed. (2) `core-admin project scout <path> --write` reads your source, proposes fitted rules via LLM, and requires you to ratify each one before delivery; if no LLM is available it presents a curated four-rule menu instead. Once both steps are done, `core-admin code audit --offline` inside that repo enforces the ratified rules immediately. Both commands work from a plain `pip install core-runtime` — the machinery floor is bundled in the wheel.
>
> **Step-by-step walkthrough** (fresh machine → violation → fix → PASS): [byor-quickstart.md](byor-quickstart.md)

The rest of this page covers the **full local runtime**. For the lightweight paths, the two commands above are the whole story.

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

Create the schema in the fresh `core` database (CORE uses a canonical
schema file, not a migration framework — see [the schema-as-truth model](how-it-works.md)):

```bash
# Apply the canonical schema to the empty database (runs psql inside the container,
# so you don't need a psql client on the host)
docker compose exec -T postgres psql -U postgres -d core < infra/sql/db_schema_live.sql
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
