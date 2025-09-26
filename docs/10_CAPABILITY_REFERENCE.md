# 10. Capability Reference

This document is the canonical, auto-generated reference for all capabilities recognized by the CORE constitution.
It is generated from the `core.knowledge_graph` database view and should not be edited manually.

## Domain: `autonomy.self_healing`

- **`autonomy.self_healing.fix_headers`**
  - **Description:** User-friendly wrapper for the header fixing logic.
  - **Source:** [src/system/admin/fixer.py](https://github.com/DariuszNewecki/CORE/blob/main/src/system/admin/fixer.py#L0)
- **`autonomy.self_healing.format_code`**
  - **Description:** Format all code in the `src` and `tests` directories using Black and Ruff with automatic fixes.
  - **Source:** [src/system/admin/fixer.py](https://github.com/DariuszNewecki/CORE/blob/main/src/system/admin/fixer.py#L0)

## Domain: `knowledge.sync`

- **`knowledge.sync.run`**
  - **Description:** Scans the codebase and syncs all symbols and their tags to the database.
  - **Source:** [src/system/admin/commands/knowledge/sync.py](https://github.com/DariuszNewecki/CORE/blob/main/src/system/admin/commands/knowledge/sync.py#L0)

## Domain: `system.bootstrap`

- **`system.bootstrap.issues`**
  - **Description:** Creates a standard set of starter issues for the project on GitHub.
  - **Source:** [src/system/admin/bootstrap.py](https://github.com/DariuszNewecki/CORE/blob/main/src/system/admin/bootstrap.py#L0)

## Domain: `system.db`

- **`system.db.migrate`**
  - **Description:** Checks for and applies pending database schema migrations.
  - **Source:** [src/system/admin/commands/db/migrate.py](https://github.com/DariuszNewecki/CORE/blob/main/src/system/admin/commands/db/migrate.py#L0)
- **`system.db.status`**
  - **Description:** Show DB connectivity and migration status.
  - **Source:** [src/system/admin/commands/db/status.py](https://github.com/DariuszNewecki/CORE/blob/main/src/system/admin/commands/db/status.py#L0)

## Domain: `system.discovery`

- **`system.discovery.cli_tree`**
  - **Description:** None
  - **Source:** [src/system/admin/commands/check/diagnostics.py](https://github.com/DariuszNewecki/CORE/blob/main/src/system/admin/commands/check/diagnostics.py#L0)

## Domain: `system.governance`

- **`system.governance.run_full_audit`**
  - **Description:** Run a full constitutional self-audit and print a summary of findings.
  - **Source:** [src/system/admin/commands/check/ci.py](https://github.com/DariuszNewecki/CORE/blob/main/src/system/admin/commands/check/ci.py#L0)

## Domain: `system.testing`

- **`system.testing.run_tests`**
  - **Description:** Run the pytest suite, optionally targeting a specific test file or capability.
  - **Source:** [src/system/admin/commands/check/ci.py](https://github.com/DariuszNewecki/CORE/blob/main/src/system/admin/commands/check/ci.py#L0)

## Domain: `system.validation`

- **`system.validation.lint`**
  - **Description:** Checks code formatting and quality using Black and Ruff.
  - **Source:** [src/system/admin/commands/check/ci.py](https://github.com/DariuszNewecki/CORE/blob/main/src/system/admin/commands/check/ci.py#L0)
