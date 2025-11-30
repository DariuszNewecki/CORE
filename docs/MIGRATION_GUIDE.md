# Migration Guide: From CommandResult to ActionResult

**Document:** Practical migration path from current state to universal atomic actions
**Timeline:** 4 weeks
**Risk:** Low (incremental, backward-compatible)
**Impact:** Foundational architecture improvement

---

## Overview

This guide provides the step-by-step process to migrate from:
- **Current:** CommandResult (fixes) + AuditCheckResult (checks) + duplicate reporters
- **Target:** ActionResult (universal) + WorkflowReporter (base) + constitutional governance

**Key Principle:** Incremental migration. No big-bang refactor. Prove pattern first.

---

## Current State Assessment

### What We Have

**✅ Good foundations:**
- CommandResult pattern working (fix.ids, fix.headers)
- DevSyncReporter beautiful output
- Activity logging infrastructure
- Constitutional .intent framework

**⚠️ Duplication:**
- Two result types (CommandResult, AuditCheckResult)
- Two reporters (AuditRunReporter, DevSyncReporter)
- Similar logic repeated

**❌ Missing:**
- Universal action abstraction
- Constitutional governance hooks
- Metadata for autonomous composition

### Migration Metrics

| Component | Current | Target | Status |
|-----------|---------|--------|--------|
| fix.ids | CommandResult | ActionResult | 🟡 Needs migration |
| fix.headers | CommandResult | ActionResult | 🟡 Needs migration |
| check.* | AuditCheckResult | ActionResult | 🟡 Needs migration |
| Reporters | 2 separate | 1 base + specialized | 🔴 Not started |
| Governance | None | Full hooks | 🔴 Not started |

---

## Phase 1: Foundation (Week 1)

**Goal:** Create ActionResult and prove it works with one action of each type.

### Day 1: Create ActionResult

**File:** `src/shared/action_types.py`

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ActionImpact(Enum):
    """Classification of action's impact on system state"""
    READ_ONLY = "read-only"
    WRITE_METADATA = "write-metadata"
    WRITE_CODE = "write-code"
    WRITE_DATA = "write-data"


@dataclass
class ActionResult:
    """
    Universal result contract for all atomic actions.

    Unifies CommandResult (for commands) and AuditCheckResult (for checks)
    into single abstraction that enables governance and composition.
    """

    action_id: str
    """Unique identifier (e.g., 'fix.ids', 'check.imports')"""

    ok: bool
    """Binary success indicator"""

    data: dict[str, Any]
    """Action-specific structured results"""

    duration_sec: float = 0.0
    """Execution time in seconds"""

    impact: ActionImpact | None = None
    """What changed (if anything)"""

    logs: list[str] = field(default_factory=list)
    """Debug trace messages (not shown to user)"""

    warnings: list[str] = field(default_factory=list)
    """Non-fatal issues encountered"""

    suggestions: list[str] = field(default_factory=list)
    """Recommended follow-up actions"""

    def __post_init__(self):
        """Validate structure"""
        if not isinstance(self.action_id, str) or not self.action_id:
            raise ValueError("action_id must be non-empty string")
        if not isinstance(self.data, dict):
            raise ValueError("data must be a dict")


# Backward compatibility aliases (temporary)
CommandResult = ActionResult  # Will deprecate
```

**Test:**
```python
# tests/shared/test_action_types.py
def test_action_result_structure():
    result = ActionResult(
        action_id="test.action",
        ok=True,
        data={"count": 42},
    )
    assert result.action_id == "test.action"
    assert result.ok is True
    assert result.data["count"] == 42
```

### Day 2: Create Metadata Decorator

**File:** `src/shared/atomic_action.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from functools import wraps

from shared.action_types import ActionImpact


@dataclass(frozen=True)
class ActionMetadata:
    """Constitutional metadata about an atomic action"""

    action_id: str
    intent: str
    impact: ActionImpact
    policies: list[str]
    category: str | None = None


def atomic_action(
    action_id: str,
    intent: str,
    impact: ActionImpact,
    policies: list[str],
    category: str | None = None,
):
    """
    Decorator marking function as constitutional atomic action.

    Attaches metadata and provides future governance hooks.
    """
    metadata = ActionMetadata(
        action_id=action_id,
        intent=intent,
        impact=impact,
        policies=policies,
        category=category,
    )

    def decorator(func):
        # Attach metadata
        func._atomic_action_metadata = metadata

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Future: Pre-execution governance hooks
            result = await func(*args, **kwargs)
            # Future: Post-execution governance hooks
            return result

        return wrapper

    return decorator


def get_action_metadata(func) -> ActionMetadata | None:
    """Extract metadata from decorated function"""
    return getattr(func, '_atomic_action_metadata', None)
```

### Day 3: Migrate fix.ids

**File:** `src/body/cli/commands/fix/metadata.py`

```python
# Change imports
from shared.action_types import ActionResult, ActionImpact
from shared.atomic_action import atomic_action

# Update function signature and decorator
@atomic_action(
    action_id="fix.ids",
    intent="Assign stable UUIDs to untagged public symbols",
    impact=ActionImpact.WRITE_METADATA,
    policies=["symbol_identification"],
    category="fixers",
)
async def fix_ids_internal(write: bool = False) -> ActionResult:
    """Core logic for fix ids command"""
    start_time = time.time()

    try:
        total_assigned = assign_missing_ids(dry_run=not write)

        return ActionResult(
            action_id="fix.ids",
            ok=True,
            data={
                "ids_assigned": total_assigned,
                "dry_run": not write,
                "mode": "write" if write else "dry-run",
            },
            duration_sec=time.time() - start_time,
            impact=ActionImpact.WRITE_METADATA,
        )

    except Exception as e:
        return ActionResult(
            action_id="fix.ids",
            ok=False,
            data={
                "error": str(e),
                "error_type": type(e).__name__,
            },
            duration_sec=time.time() - start_time,
            logs=[f"Exception during ID assignment: {e}"],
        )
```

**CLI wrapper stays same** (uses backward compat alias):
```python
async def assign_ids_command(...):
    result = await fix_ids_internal(write=write)
    # Works because ActionResult == CommandResult temporarily
```

### Day 4: Migrate check.imports (one check as proof)

**Find existing check** in audit system, migrate to ActionResult.

**File:** `src/mind/governance/checks/import_check.py`

```python
@atomic_action(
    action_id="check.imports",
    intent="Verify import grouping follows constitutional conventions",
    impact=ActionImpact.READ_ONLY,
    policies=["import_organization"],
    category="checks",
)
async def check_imports_internal() -> ActionResult:
    """Audit import organization"""
    start_time = time.time()

    violations = find_import_violations()

    return ActionResult(
        action_id="check.imports",
        ok=len(violations) == 0,
        data={
            "violations_count": len(violations),
            "violations": [v.to_dict() for v in violations],
            "files_scanned": total_files,
        },
        duration_sec=time.time() - start_time,
        impact=ActionImpact.READ_ONLY,
        suggestions=[
            "Run: core-admin fix imports --write"
        ] if violations else [],
    )
```

### Day 5: Verify & Document

**Tests:**
```bash
# Run existing tests - should pass
poetry run pytest tests/body/cli/commands/fix/test_metadata.py -v

# Run audit - should work
poetry run core-admin check audit

# Run dev-sync - should work
poetry run core-admin dev sync --dry-run
```

**Documentation:**
```markdown
# Migration Status

## Week 1 Complete ✅
- ActionResult defined
- @atomic_action decorator created
- fix.ids migrated (write action)
- check.imports migrated (read action)
- Both work with existing reporters
- Zero regressions
```

---

## Phase 2: Full Migration (Weeks 2-3)

**Goal:** Migrate all commands and checks to ActionResult.

### Week 2: Commands (fix.* and manage.*)

**Day 1-2: Remaining fix commands**
- fix.headers → ActionResult
- fix.docstrings → ActionResult
- fix.code-style → ActionResult
- fix.vector-sync → ActionResult

**Day 3-4: Manage commands**
- manage.sync-knowledge → ActionResult
- manage.define-symbols → ActionResult

**Day 5: Verification**
```bash
poetry run core-admin dev sync --write
# All commands should use ActionResult
```

### Week 3: Checks (check.*)

**Day 1-3: Migrate all checks**
- check.naming → ActionResult
- check.structure → ActionResult
- check.capabilities → ActionResult
- etc.

**Day 4: Update audit runner**
```python
# audit.py - use ActionResult instead of AuditCheckResult
for check_cls in checks:
    result: ActionResult = await check_cls.run()
    reporter.record_action_result(result)
```

**Day 5: Verification**
```bash
poetry run core-admin check audit
# All checks should use ActionResult
```

---

## Phase 3: Reporter Unification (Week 4)

**Goal:** Create WorkflowReporter base class, remove duplication.

### Day 1-2: Create WorkflowReporter

**File:** `src/body/cli/workflows/workflow_reporter.py`

```python
@dataclass
class WorkflowPhase:
    """Phase in a workflow execution"""
    name: str
    actions: list[ActionResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(a.ok for a in self.actions)


class WorkflowReporter:
    """
    Base reporter for all workflows.

    Handles common concerns:
    - Phase organization
    - Action result tracking
    - Activity logging
    - Table rendering
    - Summary generation

    Subclasses specialize formatting for specific workflows.
    """

    def __init__(self, run: ActivityRun, repo_path: str):
        self.run = run
        self.repo_path = repo_path
        self.phases: list[WorkflowPhase] = []

    def print_header(self, workflow_name: str):
        """Print workflow header"""
        console.rule(f"[bold]{workflow_name}[/bold]")
        console.print(f"[bold]Repo[/bold]     : {self.repo_path}")
        console.print(f"[bold]Run ID[/bold]   : {self.run.run_id}")
        console.print()

    def start_phase(self, name: str) -> WorkflowPhase:
        """Start new phase"""
        phase = WorkflowPhase(name=name)
        self.phases.append(phase)
        return phase

    def record_action(self, result: ActionResult, phase: WorkflowPhase):
        """Record action result"""
        phase.actions.append(result)
        log_activity(self.run, ...)

    def print_phases(self):
        """Render all phases - override for customization"""
        for phase in self.phases:
            self._print_phase(phase)

    def _print_phase(self, phase: WorkflowPhase):
        """Print single phase - override for customization"""
        # Default implementation
        pass

    def print_summary(self):
        """Print summary - override for customization"""
        # Default implementation
        pass
```

### Day 3: Specialize Reporters

**AuditReporter:**
```python
class AuditReporter(WorkflowReporter):
    """Specialized reporter for audit workflows"""

    def _print_phase(self, phase: WorkflowPhase):
        # Custom audit formatting
        # Show violations, severities, etc.
        pass
```

**DevSyncReporter:**
```python
class DevSyncReporter(WorkflowReporter):
    """Specialized reporter for dev-sync workflows"""

    def _print_phase(self, phase: WorkflowPhase):
        # Custom sync formatting
        # Show files changed, items synced, etc.
        pass
```

### Day 4-5: Remove Duplication

- Delete duplicated code from AuditRunReporter
- Delete duplicated code from DevSyncReporter
- Move shared logic to WorkflowReporter base
- Update all workflows to use new reporters

**Verify:**
```bash
poetry run core-admin check audit
poetry run core-admin dev sync --write
# Both should work with new unified reporters
```

---

## Phase 4: Governance Hooks (Post Week 4)

**Goal:** Add constitutional validation.

### Pre-execution Validation

```python
def atomic_action(...):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Validate metadata
            metadata = func._atomic_action_metadata
            validate_action_metadata(metadata)

            # Check policies exist
            for policy_id in metadata.policies:
                assert policy_exists(policy_id)

            # Execute
            result = await func(*args, **kwargs)

            # Validate result
            validate_action_result(result, metadata)

            return result
        return wrapper
    return decorator
```

### Policy Registration

```yaml
# .intent/policies/symbol_identification.yaml
policy_id: symbol_identification
description: All public symbols must have stable UUIDs
validated_by:
  - fix.ids
  - check.symbol_ids
enforced_by:
  - fix.ids
severity: medium
```

---

## Validation Checklist

### After Each Phase

- [ ] All existing tests pass
- [ ] No regressions in CLI commands
- [ ] Workflows execute successfully
- [ ] Output quality maintained
- [ ] Performance acceptable

### Final Validation

- [ ] Zero CommandResult instances (except alias)
- [ ] Zero AuditCheckResult instances
- [ ] All actions use ActionResult
- [ ] All workflows use WorkflowReporter
- [ ] Constitutional metadata present
- [ ] Governance hooks functional

---

## Rollback Plan

**If issues arise:**

1. **Week 1:** Revert files, keep CommandResult
2. **Week 2-3:** Finish migration but skip reporters
3. **Week 4:** Keep duplicate reporters if needed

**Backward compatibility:**
```python
# Temporary alias ensures nothing breaks
CommandResult = ActionResult
```

---

## Success Metrics

**Technical:**
- 100% actions using ActionResult
- 0% code duplication in reporters
- Constitutional metadata on all actions

**Governance:**
- All actions declare policies
- Validation hooks active
- Activity logging comprehensive

**User Experience:**
- CLI output quality maintained
- Performance same or better
- Error messages improved

---

## Timeline Summary

| Week | Focus | Deliverable |
|------|-------|-------------|
| 1 | Foundation | ActionResult + 2 migrated actions |
| 2 | Commands | All fix.* and manage.* migrated |
| 3 | Checks | All check.* migrated |
| 4 | Reporters | Unified WorkflowReporter |
| 5+ | Governance | Constitutional hooks active |

---

## Next Steps After Migration

Once migration complete:

1. **Enable JSON output:** `--format json` for all workflows
2. **Store in database:** Workflow runs persisted
3. **Policy enforcement:** Constitutional validation active
4. **A3 planning:** Auto-compose workflows from goals
5. **A4 foundation:** Self-modification capabilities

---

## Conclusion

This migration is not a refactoring—it's establishing CORE's foundational abstraction for autonomous operation.

**The path is clear. The papers are written. Time for the Body to follow the Mind.**
