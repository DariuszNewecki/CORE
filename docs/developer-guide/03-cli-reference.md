# CORE CLI Reference (`core-admin`)

This is the **authoritative, up‑to‑date reference** for all commands exposed by the CORE CLI.
It reflects the **actual command tree** implemented under:

```
src/body/cli/commands/
```

No deprecated, legacy, or speculative commands are included.

The CLI is built using **Typer**, and all commands follow the Mind–Body–Will model:

* **Body** executes CLI logic
* **Mind** enforces governance during audits
* **Will** (agents) participate only when invoked through governed flows

---

# 1. Top‑Level Usage

```
poetry run core-admin [COMMAND] [ARGS]
```

Print available commands:

```
poetry run core-admin --help
```

Print full command tree:

```
poetry run core-admin inspect command-tree
```

---

# 2. Command Groups

CORE’s CLI groups commands into functional domains.
Commands shown here match your real directory structure:

```
src/body/cli/commands/
├── check.py
├── coverage.py
├── develop.py
├── enrich.py
├── fix/
├── inspect.py
├── manage.py
├── mind.py
├── run.py
├── search.py
├── secrets.py
└── submit.py
```

Each section below documents only **real** commands.

---

# 3. `check` — Constitutional & Validation Checks

Run governance checks, audits, and validations.

## 3.1. Full Constitutional Audit

```
poetry run core-admin check audit
```

Runs:

* import rules
* security checks
* ID/capability hygiene
* drift detection
* naming conventions
* file header compliance
* schema validation

## 3.2. Validate Formatting/Linting/Tests

```
poetry run core-admin check validate
```

If enabled in your CLI, this triggers:

* Black
* Ruff
* syntax checks
* pytest

(If not present in your version, rely on `fix code-style` + `audit`.)

## 3.3. Check Project Status

```
poetry run core-admin check status
```

Shows quick health summary.

---

# 4. `coverage` — Coverage Inspection

```
poetry run core-admin coverage report
```

Uses:

* `coverage_analyzer`
* introspection metadata
* symbol‑level coverage mapping

Outputs summary of runtime/test coverage.

---

# 5. `develop` — Autonomous Feature Generation

Generate governed autonomous crates.

## 5.1. Develop Feature

```
poetry run core-admin develop feature "Add health endpoint"
```

Pipeline:

1. crate creation
2. context building
3. agent planning & coding
4. validation
5. constitutional audit
6. accept/reject

Crates are stored under:

```
.core/crates/<id>/
```

---

# 6. `enrich` — Context & Metadata Enrichment

Provides structural enrichments to improve function/capability metadata.

Examples (depending on your CLI):

```
poetry run core-admin enrich symbols
poetry run core-admin enrich capabilities
```

These commands call introspection services under:

```
src/features/introspection/
```

---

# 7. `fix` — Automated Self‑Healing

Located under:

```
src/body/cli/commands/fix/
```

## 7.1. Fix IDs

```
poetry run core-admin fix ids --write
```

Assigns and validates `# ID:` tags.

## 7.2. Fix Code Style (Black + Ruff)

```
poetry run core-admin fix code-style --write
```

## 7.3. Fix Docstrings

```
poetry run core-admin fix docstrings --write
```

## 7.4. Fix Headers

```
poetry run core-admin fix headers --write
```

## 7.5. Purge Legacy Tags

```
poetry run core-admin fix purge-legacy-tags --write
```

## 7.6. Fix Everything (batch)

```
poetry run core-admin fix all --dry-run
poetry run core-admin fix all --write
```

Shows/executes all non‑dangerous remediations.

---

# 8. `inspect` — Structural Inspection & Diagnostics

## 8.1. Show Command Tree

```
poetry run core-admin inspect command-tree
```

## 8.2. Inspect Project

```
poetry run core-admin inspect project
```

Shows:

* domain boundaries
* capabilities
* symbol drift
* scan summaries

(Depending on installed commands.)

---

# 9. `manage` — DB, Knowledge, Policies, Proposals

CORE stores structured knowledge in DB + `.intent/`.

## 9.1. Sync Knowledge Graph

```
poetry run core-admin manage database sync-knowledge
```

Runs:

* symbol indexing
* capability extraction
* vectorization (if configured)

## 9.2. Proposal Workflow

```
poetry run core-admin manage proposals new "Reason"
```

Creates a constitutional amendment draft.

---

# 10. `mind` — Governance Utilities

A thin wrapper around governance helpers.

Examples:

```
poetry run core-admin mind show-policies
poetry run core-admin mind show-domains
```

(Commands available vary depending on your current implementation.)

---

# 11. `run` — Execution Utilities

Utility commands for operational flows.

Examples:

```
poetry run core-admin run process-crate <id>
```

(if enabled in your version)

---

# 12. `search` — Symbol & Capability Search

Search symbols, capabilities, or files using the Knowledge Graph.

Examples:

```
poetry run core-admin search symbol "vectorizer"
poetry run core-admin search capability "audit"
```

---

# 13. `secrets` — Developer Secrets Management

Manage local secrets for development.

Examples:

```
poetry run core-admin secrets init
poetry run core-admin secrets set OPENAI_API_KEY
```

These secrets are stored locally and never committed.

---

# 14. `submit` — Workflow Submission

Used when submitting:

* proposals,
* crates (depending on workflow design),
* other structured artifacts.

Example:

```
poetry run core-admin submit proposal <path>
```

---

# 15. Quick Reference Table

| Group   | Command                 | Purpose                     |
| ------- | ----------------------- | --------------------------- |
| check   | audit                   | Full constitutional audit   |
| check   | status                  | Project health summary      |
| develop | feature                 | Autonomous crate generation |
| fix     | ids                     | Assign ID tags              |
| fix     | code-style              | Black + Ruff                |
| fix     | docstrings              | Repair docstrings           |
| fix     | headers                 | Ensure file headers         |
| fix     | purge-legacy-tags       | Remove old capability tags  |
| fix     | all                     | Batch remediation           |
| manage  | database sync-knowledge | Update Knowledge Graph      |
| manage  | proposals new           | Create amendment proposal   |
| inspect | command-tree            | Show full CLI tree          |
| search  | symbol                  | Symbol search               |
| search  | capability              | Capability search           |
| secrets | init                    | Initialize secret store     |
| secrets | set                     | Store local key             |

---

# 16. Mental Model for CLI Usage

### The CLI is the **interface to the Body**.

* It triggers validation
* It triggers audits
* It triggers agent‑based generation
* It manages constitutional workflows

Agents never modify files directly — only via CLI‑orchestrated crate flows.

The CLI is the **only safe gateway** for:

* autonomous development,
* knowledge updates,
* governance changes,
* audits and validation.

---

# 17. If Something Is Missing

If your CLI has commands not listed here,
run:

```
poetry run core-admin inspect command-tree
```

and update this document accordingly.

If this documentation ever diverges from reality,
**the documentation is wrong — fix it.**
