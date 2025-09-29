# Migration Plan: CLI V2 Refactoring

**Date:** 2025-10-26
**Status:** In Progress
**Champion:** CORE Architect AI

## 1. Goal

To refactor the `core-admin` CLI from a noun-based structure to a consistent, verb-based grammar. This will improve clarity, usability, and make the CLI easier for autonomous agents to reason about.

## 2. Constitutional Justification

This refactoring serves the following core principles:

* **`clarity_first`**: A `verb noun` grammar is more intuitive and predictable.
* **`dry_by_design`**: Consolidates overlapping concepts like `sync` and `check` into unified commands.
* **`separation_of_concerns`**: Creates a clear distinction between atomic, agent-focused commands and high-level, human-focused workflow commands.
* **`evolvable_structure`**: Allows the human-facing CLI to evolve without breaking the stable, atomic interface required for autonomy.

## 3. Proposed New Command Tree

```text
🌳 core-admin
├── 📂 check (Read-only validation & checks)
│   ├── ⚡ audit
│   ├── ⚡ lint
│   ├── ⚡ tests
│   └── ⚡ diagnostics
│
├── 📂 fix (Automated, state-changing fixes)
│   ├── ⚡ code-style
│   ├── ⚡ docstrings
│   ├── ⚡ headers
│   └── ⚡ ids
│
├── 📂 inspect (Read-only "show me" commands)
│   ├── ⚡ drift
│   ├── ⚡ status
│   └── ⚡ command-tree
│
├── 📂 manage (State-changing administrative tasks)
│   ├── 📂 database
│   │   ├── ⚡ migrate
│   │   └── ⚡ export
│   ├── 📂 keys
│   │   └── ⚡ generate
│   ├── 📂 project
│   │   ├── ⚡ new
│   │   └── ⚡ onboard
│   └── 📂 proposals
│       ├── ⚡ list
│       ├── ⚡ sign
│       └── ⚡ approve
│
├── 📂 run (Execute complex, long-running processes)
│   ├── ⚡ agent
│   ├── ⚡ vectorize
│   └── ⚡ crates
│
├── 📂 search (Discovery commands)
│   ├── ⚡ capabilities
│   └── ⚡ commands
│
└── ⚡ submit (Human-facing workflow command for integration)
```

## 4. Phased Rollout Plan

1. **Phase 1 (Parallel Build):** Implement the new command structure in a `src/cli/commands_v2/` directory, acting as adapters to the existing logic. Register them as hidden commands.
2. **Phase 2 (Ratification):** Create and approve a constitutional amendment to update `cli_governance_policy.yaml` and run a DB migration script to update the `core.cli_commands` table.
3. **Phase 3 (Cleanup):** Remove the old command files and registrations, making the V2 structure the sole implementation.
