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
poetry run core-admin dev test <file>                  # Test generation for a file
```

---

### `vectors` — Vector Store Operations (Qdrant)

CORE maintains three vector collections: `core_policies` (`.intent/` governance),
`core-patterns` (architecture patterns), and `core_specs` (`.specs/` human intent documents).

```bash
poetry run core-admin vectors sync --write             # Sync all three collections
poetry run core-admin vectors sync-code                # Sync symbol embeddings (dry-run)
poetry run core-admin vectors sync-code --write        # Apply code sync
poetry run core-admin vectors query "<query>"          # Semantic search (default: policies)
poetry run core-admin vectors query "<query>" --collection policies  # Search core_policies
poetry run core-admin vectors query "<query>" --collection patterns  # Search core-patterns
poetry run core-admin vectors query "<query>" --collection specs     # Search core_specs
poetry run core-admin vectors status                   # Vector store health and collection stats
poetry run core-admin vectors rebuild                  # Dry-run: rebuild vector collections
poetry run core-admin vectors rebuild --collection symbols --write  # Rebuild symbols
poetry run core-admin vectors cleanup                  # Clean orphaned vectors
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
poetry run core-admin runtime dashboard        # Five-panel governor dashboard (recommended)
poetry run core-admin runtime dashboard --plain  # Plain text output (pipe/watch friendly)
poetry run core-admin runtime health           # Plumbing view: workers, blackboard, crawls
```

The governor dashboard answers five questions with color signals:
1. **Convergence Direction** — is the codebase healing or accumulating debt?
2. **Governor Inbox** — are there items requiring human judgment?
3. **Loop Running** — are all workers alive and cycling?
4. **Pipeline Moving** — are proposals flowing through to execution?
5. **Autonomous Reach** — can the daemon self-heal without intervention?

```bash
watch -n 30 poetry run core-admin runtime dashboard  # Live monitoring
```

---

### `workers` — Constitutional Worker Management

```bash
poetry run core-admin workers blackboard               # Inspect the Blackboard
poetry run core-admin workers blackboard --status open # Open findings only
poetry run core-admin workers blackboard --filter "audit.violation"  # Filter by subject
poetry run core-admin workers purge --status <status> --rule <prefix> --before <hours> --write  # Purge entries
poetry run core-admin workers remediate <rule>         # Run remediation pipeline for a rule
poetry run core-admin workers remediate --file <path>  # Remediate all violations in a file
poetry run core-admin workers run <declaration>        # Run a single worker manually
```

---

### `database` — PostgreSQL State Management

```bash
poetry run core-admin database status   # Database state
poetry run core-admin database migrate  # Run migrations
poetry run core-admin database sync     # Sync database schema
```

---

### `daemon` — Background Worker Daemon

```bash
systemctl --user start core-daemon      # Start via systemd
systemctl --user stop core-daemon       # Stop
systemctl --user restart core-daemon    # Restart
journalctl --user -u core-daemon -f     # Follow logs
poetry run core-admin daemon start      # Start via CLI
```

---

### `context` — Context Packages for LLM

Every Claude Code prompt that modifies `src/` should be preceded by a context build.

```bash
poetry run core-admin context build --file <path> --task code_modification --goal "<goal>" --no-cache
poetry run core-admin context search "<query>"   # Search context evidence
pottery run core-admin context explain           # Explain context packet
```

---

### `admin` — System Forensics & Governance

```bash
poetry run core-admin admin coverage    # Governance rule coverage
poetry run core-admin admin status      # System health summary
poetry run core-admin admin traces      # Decision traces
poetry run core-admin admin health      # Admin health check
```

---

### `status` — Single-Glance System State

```bash
poetry run core-admin status drift  # System state drift
```

---

### `secrets` — Encrypted Secrets Management

```bash
poetry run core-admin secrets list      # List secret keys
poetry run core-admin secrets get <key> # Get a secret
poetry run core-admin secrets set <key> # Set a secret
poetry run core-admin secrets delete <key> # Delete a secret
```

---

### `project` — Project Lifecycle

```bash
poetry run core-admin project new      # Scaffold a new governed application
poetry run core-admin project onboard  # Onboard existing repository
poetry run core-admin project docs     # Generate project documentation
```

---

### `refactor` — Refactoring Analysis

```bash
poetry run core-admin refactor analyze <file>  # Refactoring suggestions
poetry run core-admin refactor score           # Refactoring score
poetry run core-admin refactor stats           # Refactoring statistics
poetry run core-admin refactor suggest         # Refactoring suggestions
```

---

### `interactive-test` — Interactive Test Generation

```bash
poetry run core-admin interactive-test generate  # Step-by-step test generation with approval
poetry run core-admin interactive-test info      # Test generation info
```

---

### `tools` — Governed Maintenance Tools

```bash
poetry run core-admin tools export-context   # Export context
poetry run core-admin tools rewire-imports   # Rewire import paths
```

---

## Command Conventions

**`--write`** — required for any command that modifies files or data. Without it, commands run in dry-run mode.

**Dry-run by default** — CORE never makes changes unless explicitly instructed.

**Interactive confirmation** — `dev sync --write` and destructive operations require interactive confirmation and cannot be piped.

**`--dangerous`** — some commands carry a danger flag and require explicit acknowledgment. This is by design.

---

## Governance Note

All CLI operations that modify files are subject to constitutional governance. A command that would produce a blocking violation halts before applying changes. The CLI is not an escape hatch from the constitution.
