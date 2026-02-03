# Resource-First CLI Architecture

**Status:** ✅ Proof of Concept (Database Resource Complete)
**Version:** 2.0.0
**Governed By:** `.intent/rules/cli/interface_design.json`

---

## Overview

The resource-first CLI architecture replaces the legacy layer-based command structure with a user-intent-driven design that follows industry standards (kubectl, AWS CLI).

### Before (Legacy)
```bash
core-admin manage database sync        # Layer-based, verbose
core-admin body check tests           # Exposes architecture
core-admin fix all                    # Unclear scope
```

### After (Resource-First)
```bash
core-admin database sync              # Clear resource target
core-admin code test                  # User mental model
core-admin code fix                   # Intuitive action
```

---

## Constitutional Principles

From `.intent/rules/cli/interface_design.json`:

1. **Resource-First Pattern** - Commands follow `resource action [flags]` (depth=2)
2. **No Layer Exposure** - Forbidden names: `mind`, `body`, `will`, `manage`, `check`, `fix`
3. **Standard Verbs** - Actions use consistent vocabulary across resources
4. **Dangerous Explicit** - State mutations require `--write` flag
5. **Async Execution** - All async commands wrapped with `@core_command`
6. **Fail-Fast Discovery** - Module load errors are blocking unless `CORE_DEV_MODE=1`
7. **Help Required** - Every command provides help text and examples

---

## Database Resource (Reference Implementation)

### Structure

```
src/body/cli/resources/database/
├── __init__.py       # Exports Typer app
├── sync.py          # Synchronize schema & data
├── migrate.py       # Run Alembic migrations
├── export.py        # Export to JSON/SQL
├── cleanup.py       # Remove stale data
└── status.py        # Health metrics
```

### Commands

#### `core-admin database sync`
Synchronizes PostgreSQL schema and seeds constitutional data.

```bash
# Dry-run (show what would change)
core-admin database sync

# Apply changes
core-admin database sync --write

# Force sync (skip confirmations)
core-admin database sync --write --force
```

**Constitutional Compliance:**
- ✅ Enforces `governance.artifact_mutation.traceable`
- ✅ Generates audit trail
- ✅ Creates rollback plan

---

#### `core-admin database migrate`
Runs pending Alembic migrations.

```bash
# Show pending migrations
core-admin database migrate

# Apply all pending
core-admin database migrate --write

# Migrate to specific revision
core-admin database migrate --write --revision abc123
```

---

#### `core-admin database export`
Exports database contents to file.

```bash
# Export all tables to JSON
core-admin database export

# Export specific tables
core-admin database export --tables "symbols,cli_commands"

# Export to SQL format
core-admin database export --format sql --output backup.sql
```

**Constitutional Compliance:**
- ✅ Writes to `var/` directory (runtime artifacts)
- ✅ Uses `FileHandler` for traceable mutations

---

#### `core-admin database cleanup`
Removes orphaned and stale records.

```bash
# Dry-run: show what would be deleted
core-admin database cleanup

# Clean up old memory entries
core-admin database cleanup --target memory --write

# Full cleanup with custom age threshold
core-admin database cleanup --target all --days 60 --write
```

**Targets:**
- `memory` - Old conversation memory entries
- `sessions` - Expired session data
- `orphans` - Records without valid foreign keys
- `all` - Run all cleanup operations

---

#### `core-admin database status`
Shows health metrics and diagnostics.

```bash
# Basic status
core-admin database status

# Detailed table statistics
core-admin database status --detailed

# JSON output for scripting
core-admin database status --format json
```

**Displays:**
- Connection status
- Database size
- Table row counts
- Index health
- Recent activity

---

## Validation Framework

### Resource Name Validation

```python
from shared.cli_framework import validate_resource_name

# ✅ Valid
validate_resource_name("database")
validate_resource_name("my-resource")

# ❌ Forbidden (layer exposure)
validate_resource_name("body")  # Raises ConstitutionalViolation

# ❌ Invalid format
validate_resource_name("Database")  # Must be lowercase
validate_resource_name("data_base")  # Only hyphens allowed
```

### Action Name Validation

```python
from shared.cli_framework import validate_action_name

# ✅ Standard verbs (no warnings)
validate_action_name("database", "sync")
validate_action_name("database", "query")

# ⚠️ Non-standard (warning logged)
validate_action_name("database", "foobar")
```

### Command Depth Validation

```python
from shared.cli_framework import validate_command_depth

# ✅ Valid patterns
validate_command_depth("database sync")          # depth=2
validate_command_depth("admin config sync")      # depth=3 (admin exception)

# ❌ Invalid patterns
validate_command_depth("database foo bar")       # depth=3 (non-admin)
validate_command_depth("foo bar baz qux")        # depth=4 (too deep)
```

---

## Creating New Resources

### Step 1: Create Resource Directory

```bash
mkdir -p src/body/cli/resources/myresource
```

### Step 2: Initialize Resource Module

```python
# src/body/cli/resources/myresource/__init__.py
"""My resource commands."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="myresource",
    help="My resource operations",
    no_args_is_help=True,
)

# Import command modules to register them
from . import action1, action2

__all__ = ["app"]
```

### Step 3: Create Action Command

```python
# src/body/cli/resources/myresource/action1.py
"""Action command for myresource."""

from __future__ import annotations

import typer
from rich.console import Console

from shared.cli_utils import core_command
from shared.context import CoreContext

from . import app

console = Console()

@app.command("action1")
@core_command(dangerous=False, requires_context=True)
async def action1_command(
    ctx: typer.Context,
    flag: bool = typer.Option(False, "--flag", help="Example flag"),
) -> None:
    """
    Description of action1.

    Examples:
        core-admin myresource action1
        core-admin myresource action1 --flag
    """
    core_context: CoreContext = ctx.obj

    console.print("[bold cyan]Running action1...[/bold cyan]")

    # Implementation here
    # Delegate to service layer, not inline logic

    console.print("[green]✅ Action completed[/green]")
```

### Step 4: Register Resource (Discovery)

Resources are auto-discovered from `src/body/cli/resources/` - no manual registration needed.

The discovery system:
1. Scans `resources/` directory
2. Validates resource names
3. Imports modules
4. Registers Typer apps
5. Fails fast on errors (unless `CORE_DEV_MODE=1`)

---

## Testing

### Unit Tests (Validation)

```python
# tests/unit/cli/test_myresource_validation.py
import pytest
from shared.cli_framework import validate_resource_name

def test_myresource_name_valid():
    validate_resource_name("myresource")  # Should not raise
```

### Integration Tests (Commands)

```python
# tests/integration/cli/test_myresource.py
from typer.testing import CliRunner
from body.cli.resources.myresource import app

runner = CliRunner()

def test_action1_help():
    result = runner.invoke(app, ["action1", "--help"])
    assert result.exit_code == 0
    assert "action1" in result.stdout
```

---

## Migration Path

### Phase 1: Additive (Current)
- ✅ New resources added alongside legacy commands
- ✅ Both patterns work simultaneously
- ✅ No breaking changes

### Phase 2: Deprecation (v2.1.0 - v2.9.0)
- Add deprecation warnings to legacy commands
- Update documentation to show new patterns
- Announce removal timeline

### Phase 3: Removal (v3.0.0)
- Remove legacy command structure
- Keep only resource-first pattern
- Breaking change clearly communicated

---

## Design Rationale

### Why Resource-First?

**User Mental Model**
- Users think: "I want to sync THE DATABASE"
- Not: "I want to manage the database by syncing"

**Industry Standards**
- `kubectl get pods` not `kubectl manage pods get`
- `aws s3 ls` not `aws manage s3 list`
- `docker container start` not `docker manage container start`

**Discoverability**
- `core-admin database` → see all database operations
- Tab completion works naturally
- Help text at every level

**Constitutional Alignment**
- CLI = interface (what users see)
- Mind/Body/Will = implementation (what users don't see)
- Separation of concerns maintained

---

## Next Resources to Implement

Priority order based on usage frequency:

1. ✅ **database** (Complete)
2. **code** - Codebase operations (format, lint, test, fix)
3. **vectors** - Qdrant operations (sync, query, rebuild)
4. **symbols** - Symbol registry (sync, inspect, fix-ids)
5. **constitution** - Governance (validate, audit, query)
6. **proposals** - Autonomy workflow (create, approve, execute)
7. **project** - Project lifecycle (new, onboard, docs)
8. **dev** - Developer workflows (sync, test-interactive)

---

## References

- Constitutional Rules: `.intent/rules/cli/interface_design.json`
- Validation Framework: `src/shared/cli_framework/validation.py`
- Database Resource: `src/body/cli/resources/database/`
- Tests: `tests/unit/cli/test_cli_validation.py`

---

**Status**: Database resource complete and validated. Ready for production use and replication to other resources.
