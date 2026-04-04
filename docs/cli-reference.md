# CLI Reference

```
core-admin [command group] [subcommand] [options]
```

Run `poetry run core-admin <group> --help` for the full subcommand list of any group.

---

### `code` — Codebase Quality & Verification

```bash
poetry run core-admin code audit          # Constitutional audit (all rules, all engines)
poetry run core-admin code lint           # Black + Ruff check (read-only)
poetry run core-admin code test           # Run pytest suite
poetry run core-admin code format         # Format code
poetry run core-admin code complexity     # Complexity analysis
poetry run core-admin code clarity        # Clarity refactoring
poetry run core-admin code docstrings     # Docstring compliance
poetry run core-admin code actions        # List registered Atomic Actions
poetry run core-admin code integrity      # Integrity checks
poetry run core-admin code check-imports  # Import boundary checks
```

---

### `constitution` — Governance & Policy

```bash
poetry run core-admin constitution audit     # Audit constitution rules
poetry run core-admin constitution status    # Enforcement coverage (enforced vs declared)
poetry run core-admin constitution validate  # Validate .intent/ schemas and policies
poetry run core-admin constitution query     # Semantic search over constitutional rules
```

---

### `proposals` — Autonomous Proposal Workflow

The human-in-the-loop gate for autonomous system modification.

```bash
poetry run core-admin proposals create        # Create a new proposal
poetry run core-admin proposals list          # List proposals and risk assessments
poetry run core-admin proposals show <id>     # Detailed breakdown of a proposal
poetry run core-admin proposals approve <id>  # Authorize for execution
poetry run core-admin proposals reject <id>   # Reject proposal
poetry run core-admin proposals execute <id>  # Execute approved proposal
```

---

### `dev` — Developer Workflows

```bash
poetry run core-admin dev sync                         # Dry-run: preview knowledge graph sync
poetry run core-admin dev sync --write                 # Sync (interactive confirmation required)
poetry run core-admin dev chat                         # AI chat for development assistance
poetry run core-admin dev refactor <goal>              # Autonomous refactoring toward a goal
poetry run core-admin dev refactor <goal> --write      # Apply refactoring
poetry run core-admin dev strategic-audit              # Dry-run: full self-awareness cycle
poetry run core-admin dev strategic-audit --write      # Persist campaign to DB
poetry run core-admin dev strategic-audit --write --execute  # Persist + execute autonomously
poetry run core-admin dev stability                    # Stability checks
poetry run core-admin dev test <file>                  # Test generation for a file
```

---

### `vectors` — Vector Store Operations (Qdrant)

```bash
poetry run core-admin vectors sync-code               # Sync symbol embeddings (dry-run)
poetry run core-admin vectors sync-code --write       # Apply sync
poetry run core-admin vectors rebuild                 # Dry-run: rebuild vector collections
poetry run core-admin vectors rebuild --collection symbols --write  # Rebuild symbols
poetry run core-admin vectors rebuild --collection all --write      # Rebuild all
```

---

### `symbols` — Knowledge Graph & Symbol Registry

```bash
poetry run core-admin symbols status   # Symbol registry status
poetry run core-admin symbols audit    # Audit symbol assignments
poetry run core-admin symbols sync     # Sync symbol registry
```

---

### `runtime` — Runtime State & Health

```bash
poetry run core-admin runtime status  # Runtime health
```

---

### `database` — PostgreSQL State Management

```bash
poetry run core-admin database status   # Database state
poetry run core-admin database migrate  # Run migrations
```

---

### `daemon` — Background Worker Daemon

```bash
systemctl --user restart core-daemon    # Restart via systemd
poetry run core-admin daemon status     # Daemon status via CLI
```

---

### `status` — Single-Glance System State

```bash
poetry run core-admin status  # Full system readiness at a glance
```

---

### `admin` — System Forensics

```bash
poetry run core-admin admin traces    # Decision traces
poetry run core-admin admin refusals  # Agent refusal analytics
```

---

### `workers` — Constitutional Worker Management

```bash
poetry run core-admin workers list    # List workers
poetry run core-admin workers status  # Worker status
```

---

### `secrets` — Encrypted Secrets Management

```bash
poetry run core-admin secrets list      # List secret keys
poetry run core-admin secrets set <key> # Set a secret
```

---

### `project` — Project Lifecycle

```bash
poetry run core-admin project new      # Scaffold a new governed application
poetry run core-admin project onboard  # Onboard existing repository
poetry run core-admin project docs     # Generate project documentation
```

---

### `context` — Context Packages for LLM

```bash
poetry run core-admin context build    # Build a context package
poetry run core-admin context validate # Validate a context package
poetry run core-admin context show     # Inspect a context package
```

---

### `refactor` — Refactoring Analysis

```bash
poetry run core-admin refactor analyze <file>  # Refactoring suggestions
```

---

### `interactive-test` — Interactive Test Generation

```bash
poetry run core-admin interactive-test  # Step-by-step test generation with approval
```

---

### `tools` — Governed Maintenance Tools

```bash
poetry run core-admin tools  # List available maintenance tools
```

---

## Command Conventions

**`--write`** — required for any command that modifies files. Without it, commands run in dry-run mode.

**Dry-run by default** — CORE never makes changes unless explicitly instructed.

**Interactive confirmation** — `dev sync --write` and destructive operations require interactive confirmation and cannot be piped.

**`--dangerous`** — some commands carry a danger flag and require explicit acknowledgment. This is by design.

---

## Governance Note

All CLI operations that modify files are subject to constitutional governance. A command that would produce a blocking violation halts before applying changes. The CLI is not an escape hatch from the constitution.
