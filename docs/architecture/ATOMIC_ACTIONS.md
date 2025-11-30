# CORE Atomic Actions Architecture

**Status:** Foundational Pattern
**Version:** 1.0.0
**Last Updated:** 2025-11-30
**Constitutional Reference:** `.intent/charter/patterns/atomic_actions.yaml`

---

## Executive Summary

CORE is not a collection of CLI commands—it is a **constitutional system of composable atomic actions**. This document defines the fundamental abstraction that enables:
- Autonomous operation with governance
- Composable workflows
- Scalable oversight (A2 → A3 → A4)
- Constitutional compliance at every layer

**Key Insight:** Every operation in CORE—whether reading (audit checks), writing (fixes), or transforming (sync)—is an atomic action governed by the same constitutional principles.

---

## Table of Contents

1. [The Problem](#the-problem)
2. [The Atomic Action Abstraction](#the-atomic-action-abstraction)
3. [The Universal Contract](#the-universal-contract)
4. [Workflow Orchestration](#workflow-orchestration)
5. [Constitutional Governance](#constitutional-governance)
6. [Migration Path](#migration-path)
7. [Implementation Guide](#implementation-guide)
8. [Future Vision](#future-vision)

---

## The Problem

### What We Had

**Before CommandResult pattern:**
```python
def fix_ids():
    total = assign_missing_ids()
    print(f"Fixed {total} IDs")  # No structure
    # Returns nothing useful
```

**Problems:**
- No standard result format
- Can't compose commands
- Can't test without CLI
- No governance hooks
- Every command improvises output

### What We Have Now

**After CommandResult pattern (partial):**
```python
async def fix_ids_internal() -> CommandResult:
    total = assign_missing_ids()
    return CommandResult(
        name="fix.ids",
        ok=True,
        data={"ids_assigned": total}
    )
```

**Better, but:**
- `CommandResult` for commands
- `AuditCheckResult` for checks
- Two different contracts for the same abstraction
- Reporters duplicated (AuditRunReporter vs DevSyncReporter)
- Still no universal governance

### What We Need

**One universal abstraction:**
```python
async def fix_ids_internal() -> ActionResult:
    """Atomic action: Assign stable IDs"""
    # ... implementation
    return ActionResult(
        action_id="fix.ids",
        ok=True,
        data={"ids_assigned": total}
    )

async def check_imports_internal() -> ActionResult:
    """Atomic action: Validate imports"""
    # ... implementation
    return ActionResult(
        action_id="check.imports",
        ok=True,
        data={"violations": violations}
    )
```

**Why this matters:**
- Universal contract = universal governance
- Same orchestration for checks and fixes
- One reporter system
- Constitutional policies apply uniformly
- Enables autonomous composition

---

## The Atomic Action Abstraction

### Definition

An **atomic action** is the fundamental unit of autonomous operation in CORE. It:

1. **Does ONE thing** - Clear, singular purpose
2. **Returns structured results** - ActionResult contract
3. **Respects constitutional constraints** - Governed by Mind layer
4. **Composes with other actions** - Building block for workflows
5. **Logs to activity stream** - Full audit trail

### Examples

**Read Action (Check):**
```python
@atomic_action(
    action_id="check.imports",
    intent="Verify import grouping follows conventions",
    impact="read-only",
    policies=["import_organization"]
)
async def check_imports_internal() -> ActionResult:
    violations = find_import_violations()
    return ActionResult(
        action_id="check.imports",
        ok=len(violations) == 0,
        data={
            "violations_count": len(violations),
            "violations": violations,
            "files_scanned": count,
        }
    )
```

**Write Action (Fix):**
```python
@atomic_action(
    action_id="fix.ids",
    intent="Assign stable UUIDs to untagged symbols",
    impact="write-metadata",
    policies=["symbol_identification"]
)
async def fix_ids_internal(write: bool) -> ActionResult:
    total = assign_missing_ids(dry_run=not write)
    return ActionResult(
        action_id="fix.ids",
        ok=True,
        data={
            "ids_assigned": total,
            "dry_run": not write,
        }
    )
```

**Transform Action (Sync):**
```python
@atomic_action(
    action_id="sync.knowledge",
    intent="Synchronize filesystem to database",
    impact="write-data",
    policies=["knowledge_integrity"]
)
async def sync_knowledge_internal(write: bool) -> ActionResult:
    result = synchronize_symbols(dry_run=not write)
    return ActionResult(
        action_id="sync.knowledge",
        ok=result.success,
        data={
            "symbols_synced": result.count,
            "symbols_added": result.added,
            "symbols_updated": result.updated,
        }
    )
```

---

## The Universal Contract

### ActionResult Structure

```python
@dataclass
class ActionResult:
    """
    Universal result contract for all atomic actions.

    Replaces CommandResult and AuditCheckResult with single abstraction.
    """

    action_id: str
    """Unique identifier (e.g., 'fix.ids', 'check.imports')"""

    ok: bool
    """Binary success indicator"""

    data: dict[str, Any]
    """Action-specific structured results"""

    duration_sec: float = 0.0
    """Execution time"""

    impact: ActionImpact | None = None
    """What changed: read-only, write-metadata, write-code, write-data"""

    logs: list[str] = field(default_factory=list)
    """Debug trace messages (not shown to user by default)"""

    warnings: list[str] = field(default_factory=list)
    """Non-fatal issues encountered"""

    suggestions: list[str] = field(default_factory=list)
    """Recommended follow-up actions"""
```

### Action Metadata (Decorator)

```python
@dataclass
class ActionMetadata:
    """Metadata about an atomic action (Mind-layer definition)"""

    action_id: str
    """Unique identifier"""

    intent: str
    """Human-readable purpose"""

    impact: ActionImpact
    """read-only | write-metadata | write-code | write-data"""

    policies: list[str]
    """Constitutional policies this action validates/enforces"""

    category: str | None = None
    """Logical grouping (e.g., 'fixers', 'checks', 'sync')"""
```

### Why This Works

**For Checks:**
```python
ActionResult(
    action_id="check.imports",
    ok=True,  # No violations
    data={"violations_count": 0, "files_scanned": 353}
)
```

**For Fixes:**
```python
ActionResult(
    action_id="fix.headers",
    ok=True,  # Successfully fixed
    data={"violations_found": 1, "fixed_count": 1}
)
```

**For Sync:**
```python
ActionResult(
    action_id="sync.knowledge",
    ok=True,  # Sync succeeded
    data={"symbols_synced": 150, "symbols_added": 3}
)
```

Same structure. Same governance. Same reporting. Different semantics.

---

## Workflow Orchestration

### Definition

A **workflow** is a constitutionally governed composition of atomic actions organized into phases to achieve a declared goal.

Workflows are NOT scripts—they are **governance structures**.

### Workflow Contract

```python
@dataclass
class WorkflowDefinition:
    """Mind-layer definition of a workflow"""

    workflow_id: str
    """Unique identifier (e.g., 'check.audit', 'dev.sync')"""

    goal: str
    """What success means"""

    phases: list[WorkflowPhase]
    """Logical groupings of actions"""

    abort_policy: AbortPolicy
    """When to stop: stop_on_any | stop_on_critical | continue_all"""

    retry_policy: RetryPolicy | None = None
    """How to handle transient failures"""


@dataclass
class WorkflowPhase:
    """A logical grouping of related actions"""

    name: str
    """Human-readable phase name"""

    actions: list[str]
    """Action IDs to execute in this phase"""

    critical: bool = True
    """If False, phase failures don't abort workflow"""
```

### Example: Audit Workflow

```python
audit_workflow = WorkflowDefinition(
    workflow_id="check.audit",
    goal="Verify complete constitutional compliance",
    phases=[
        WorkflowPhase(
            name="Knowledge Graph",
            actions=["build.knowledge_graph"],
            critical=True
        ),
        WorkflowPhase(
            name="Constitutional Checks",
            actions=[
                "check.imports",
                "check.naming",
                "check.structure",
                "check.capabilities",
            ],
            critical=False  # Show all violations, don't abort
        ),
    ],
    abort_policy=AbortPolicy.CONTINUE_ALL,
)
```

### Example: Sync Workflow

```python
sync_workflow = WorkflowDefinition(
    workflow_id="dev.sync",
    goal="Synchronize development environment to compliant state",
    phases=[
        WorkflowPhase(
            name="Code Fixers",
            actions=["fix.ids", "fix.headers", "fix.docstrings"],
            critical=True
        ),
        WorkflowPhase(
            name="Quality Checks",
            actions=["check.lint"],
            critical=False  # Informational
        ),
        WorkflowPhase(
            name="Database Sync",
            actions=["sync.vectors", "sync.knowledge"],
            critical=True
        ),
    ],
    abort_policy=AbortPolicy.STOP_ON_CRITICAL,
)
```

---

## Constitutional Governance

### Principles

1. **Every action is governed**
   No action executes outside constitutional oversight.

2. **Composition preserves governance**
   When actions compose into workflows, constraints propagate.

3. **Failures are constitutional events**
   Not exceptions—governed states that trigger decisions.

4. **Autonomy requires governance**
   A3/A4 need MORE oversight, not less.

### Enforcement Points

**Pre-execution:**
```python
# Validate action metadata
assert action.metadata.action_id in registered_actions
assert all(policy in constitutional_policies for policy in action.metadata.policies)
assert action.metadata.impact in [ActionImpact.READ_ONLY, ...]
```

**During execution:**
```python
# Activity logging (already implemented)
with activity_run(workflow_id) as run:
    log_activity(run, event=f"action:{action_id}", status="start")
    result = await action()
    log_activity(run, event=f"action:{action_id}", status="ok" if result.ok else "error")
```

**Post-execution:**
```python
# Validate result structure
assert isinstance(result, ActionResult)
assert result.action_id == expected_action_id
assert isinstance(result.data, dict)

# Store for governance review (future)
await governance_db.store_action_result(result)
```

### Constitutional Policies

Actions declare which policies they validate:

```yaml
# .intent/policies/symbol_identification.yaml
policy_id: symbol_identification
description: All public symbols must have stable UUIDs
validated_by:
  - fix.ids
  - check.symbol_ids
severity: medium
remediation: "Run: core-admin fix ids --write"
```

---

## Migration Path

### Current State

```
CommandResult (fix.*)  ←─┐
                           ├─ Need unification
AuditCheckResult (check.*) ←─┘

AuditRunReporter ←─┐
                    ├─ Need unification
DevSyncReporter    ←─┘
```

### Target State

```
ActionResult (universal)
    ↓
WorkflowReporter (base)
    ├─ AuditReporter (specialized)
    └─ DevSyncReporter (specialized)
```

### Phase 1: Unification (Week 1)

**Create the abstractions:**
1. `ActionResult` class (merge CommandResult + AuditCheckResult)
2. `WorkflowReporter` base class
3. `@atomic_action` decorator

**Prove the pattern:**
1. Migrate `fix.ids` to ActionResult
2. Migrate `check.imports` to ActionResult
3. Show both work with same reporter

**Success criteria:**
- One action of each type (read, write) using ActionResult
- WorkflowReporter renders both beautifully
- No regressions in existing functionality

### Phase 2: Migration (Weeks 2-3)

**Migrate all actions:**
1. All `fix.*` commands → ActionResult
2. All `check.*` commands → ActionResult
3. All `manage.*` commands → ActionResult
4. All `run.*` commands → ActionResult

**Update reporters:**
1. AuditReporter extends WorkflowReporter
2. DevSyncReporter extends WorkflowReporter
3. Remove duplicated code

**Success criteria:**
- Zero CommandResult instances
- Zero AuditCheckResult instances
- All workflows use WorkflowReporter

### Phase 3: Governance (Week 4)

**Add validation hooks:**
1. Pre-execution: validate action metadata
2. During: enforce constitutional policies
3. Post: store results for review

**Enable composition:**
1. Workflow DAG validation
2. Transitive policy checking
3. Auto-generated documentation

**Success criteria:**
- All actions have constitutional metadata
- Policies enforce at runtime
- Violations trigger governance events

### Phase 4: Autonomy (Month 2+)

**A3 capabilities:**
1. Actions declare capabilities they provide
2. Goal planner auto-composes workflows
3. Self-healing on failures

**A4 foundations:**
1. Actions can modify actions
2. Workflows can modify workflows
3. Constitutional amendment process

---

## Implementation Guide

### Step 1: Define ActionResult

```python
# src/shared/action_types.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ActionImpact(Enum):
    """What an action changes"""
    READ_ONLY = "read-only"
    WRITE_METADATA = "write-metadata"
    WRITE_CODE = "write-code"
    WRITE_DATA = "write-data"


@dataclass
class ActionResult:
    """Universal result contract for all atomic actions"""

    action_id: str
    ok: bool
    data: dict[str, Any]
    duration_sec: float = 0.0
    impact: ActionImpact | None = None
    logs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
```

### Step 2: Create Decorator

```python
# src/shared/atomic_action.py
from functools import wraps


@dataclass
class ActionMetadata:
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
    """Decorator to mark a function as an atomic action"""

    metadata = ActionMetadata(
        action_id=action_id,
        intent=intent,
        impact=impact,
        policies=policies,
        category=category,
    )

    def decorator(func):
        func._atomic_action_metadata = metadata

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Future: Add governance hooks here
            return await func(*args, **kwargs)

        return wrapper

    return decorator
```

### Step 3: Migrate One Action

```python
# Before
async def fix_ids_internal(write: bool) -> CommandResult:
    ...

# After
@atomic_action(
    action_id="fix.ids",
    intent="Assign stable UUIDs to untagged public symbols",
    impact=ActionImpact.WRITE_METADATA,
    policies=["symbol_identification"],
    category="fixers",
)
async def fix_ids_internal(write: bool) -> ActionResult:
    start_time = time.time()

    try:
        total = assign_missing_ids(dry_run=not write)

        return ActionResult(
            action_id="fix.ids",
            ok=True,
            data={
                "ids_assigned": total,
                "dry_run": not write,
            },
            duration_sec=time.time() - start_time,
            impact=ActionImpact.WRITE_METADATA,
        )
    except Exception as e:
        return ActionResult(
            action_id="fix.ids",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start_time,
        )
```

---

## Future Vision

### A3: Autonomous Goal Planning

```python
# User declares goal
goal = "Achieve full constitutional compliance"

# System plans workflow
planner = AutonomousPlanner()
workflow = await planner.plan_workflow(goal)

# System shows plan
print(workflow.phases)
# Phase 1: Run all checks
# Phase 2: Auto-fix violations
# Phase 3: Verify compliance

# User approves
if confirm("Execute this plan?"):
    await workflow.execute()
```

### A4: Self-Modification

```python
# System detects inefficiency
if action.duration_sec > threshold:
    # System proposes improvement
    improvement = await optimizer.suggest_improvement(action)

    # Constitutional review
    if await constitution.approve(improvement):
        # System modifies itself
        await action.update_implementation(improvement)
```

---

## Conclusion

Atomic actions are not just a refactoring—they are CORE's foundational abstraction for autonomous operation with constitutional governance.

By establishing this universal contract, we enable:
- Composable workflows
- Scalable oversight
- Autonomous planning (A3)
- Self-modification (A4)

**The papers are written. Now the Body can follow the Mind.**

---

## References

- Constitutional Pattern: `.intent/charter/patterns/atomic_actions.yaml`
- Workflow Pattern: `docs/patterns/WORKFLOW_ORCHESTRATION.md`
- Related Commits:
  - `908477d`: CommandResult pattern introduction
  - Current: DevSyncReporter implementation
