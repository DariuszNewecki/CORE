# Getting Started

## Two ways to use CORE

You don't need the full runtime to start. Pick the path that matches your goal:

| Goal | Path | What you need |
|------|------|---------------|
| **Govern my repo in CI** | [GitHub Action](cold-reviewer.md) — runs the constitutional audit on every PR, no local install | A GitHub repo |
| **Run an audit locally, no services** | `pip install core-runtime` then `core-admin code audit --offline` — skips `knowledge_gate`/`llm_gate` (they need a DB + LLM), reports the skip | Python 3.12+ |
| **Run the full thesis** (encounter → audit → remediate → verify, the autonomous daemon) | The full local runtime below | Postgres + Qdrant + an LLM resource |

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
and finishes by showing CORE govern itself (no LLM key needed for the demo):

```bash
git clone https://github.com/DariuszNewecki/CORE.git
cd CORE
./install-core.sh
```

If that succeeds you can skip to [Key Commands](#key-commands) — CORE is running.
The rest of this section is the same path, done by hand.

### Manual installation

```bash
git clone https://github.com/DariuszNewecki/CORE.git
cd CORE
poetry install

cp .env.example .env
# Edit .env: set DATABASE__URL / QDRANT__URL if they differ from the defaults,
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
(`core-admin daemon up`), the full audit runs every engine:

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

CORE uses Qdrant for semantic search across constitutional documents and architectural papers. Sync the vector collections after installation:

```bash
poetry run core-admin vectors sync --write
```

This indexes `.intent/` governance documents and `.specs/` architectural papers into searchable vector collections. Context builds draw evidence from these collections.

---

## Key Commands

Sync the knowledge graph after code changes:

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

---

## Next Steps

- [How It Works](how-it-works.md) — understand the constitutional model before making changes
- [CLI Reference](cli-reference.md) — full command reference
- [Contributing](contributing.md) — if you want to engage with the project
