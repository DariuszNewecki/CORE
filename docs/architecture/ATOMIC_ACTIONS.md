# CORE Atomic Actions Architecture

**Status:** Foundational Pattern
**Version:** 2.0.0
**Last Updated:** 2025-11-30
**Constitutional Reference:** `.intent/charter/patterns/atomic_actions.yaml`

---

## Executive Summary

CORE is not a collection of CLI commands—it is a **constitutional system of composable atomic actions**.

Like a brick layer who doesn't make bricks but builds with them, CORE composes small, focused building blocks into larger structures. Atomic actions are those fundamental bricks:

- **One brick = One thing** (UNIX philosophy)
- **Small and focused** (30 small files > 1 giant file)
- **Clear contracts** (ActionResult = predictable shape)
- **Compose upward** (small → medium → large → features → CORE)

**Key Insight:** Every operation in CORE—whether reading (checks), writing (fixes), or transforming (sync)—is an atomic action. Not because of decorators or metadata pollution, but because of its **structure, contract, and registration in the system.**

---

## Table of Contents

1. [The Problem](#the-problem)
2. [The Philosophy](#the-philosophy)
3. [The Universal Contract](#the-universal-contract)
4. [Discovery & Governance](#discovery--governance)
5. [Composition Over Complexity](#composition-over-complexity)
6. [Constitutional Enforcement](#constitutional-enforcement)
7. [Implementation Guide](#implementation-guide)
8. [Migration Path](#migration-path)

---

## The Problem

### Kitchen Sink Anti-Pattern

Code naturally drifts toward complexity:

```python
def fix_everything():
    """Does way too many things"""
    # 500 lines of chaos
    assign_missing_ids()
    fix_headers()
    format_code()
    sync_database()
    update_vectors()
    generate_reports()
    send_notifications()
    # ... keeps growing forever
```

**Problems:**
- Impossible to reuse
- Hard to test
- Violates single responsibility
- Can't compose with other actions
- No clear success/failure contract

### What We Had Before

**Random return types:**
```python
def check_imports():
    print("Checking imports...")  # Side effects
    return violations  # List? Dict? None?

def fix_ids():
    total = do_work()
    # Returns nothing useful
```

**No structure, no contract, no composability.**

---

## The Philosophy

### The Brick Layer's Mental Model

**You are not a programmer writing code.** You are an architect who:

1. **Specifies what must exist** (`.intent/` - the blueprints)
2. **Defines how bricks fit together** (patterns)
3. **States why they're needed** (intent, goals)

Then:
- **CORE reads the blueprints** (`.intent/` files)
- **LLMs build the bricks** (generate code)
- **DB/Qdrant oversee the work** (validate patterns)
- **Constitutional checks enforce quality** (canary testing)

### The UNIX Philosophy Applied

**"Do one thing and do it well"** - but at scale:

```
Level 1: Atomic Actions (bricks)
  ├─ assign_id_to_symbol()      ← 30 lines, one thing
  ├─ validate_id_format()       ← 20 lines, one thing
  └─ write_id_to_file()         ← 25 lines, one thing

Level 2: Composed Actions (walls)
  └─ fix_ids_internal()         ← Composes 3 bricks
      └─ calls: validate → assign → write

Level 3: Workflows (rooms)
  └─ dev_sync()                 ← Composes multiple actions
      └─ calls: fix_ids → fix_headers → check_lint

Level 4: Features (house)
  └─ autonomous_development     ← Composes workflows
```

**Key principle:** Build UP through composition, not OUT through bloat.

### Source Code Purity

**MAXIMUM allowed pollution:** IDs only.

```python
# ID: 8be64ae4-477d-4166-b7bf-bbb7a77a4c6c
async def fix_ids_internal(write: bool) -> ActionResult:
    """
    Assign stable UUIDs to untagged public symbols.

    Pattern: action_pattern
    Impact: write-metadata
    Policies: symbol_identification
    """
```

**Why IDs are tolerated:**
- Refactoring breaks everything without them
- Stable reference across file moves
- Links code to DB/Qdrant entries

**What is FORBIDDEN:**

```python
# ❌ WRONG - Metadata pollution
@atomic_action(
    action_id="fix.ids",
    intent="Assign UUIDs",
    impact=ActionImpact.WRITE_METADATA,
    policies=["symbol_identification"],
    category="fixers",
    timeout=300,
    retry_count=3,
)
```

**Why forbidden:**
- Duplicates what's in docstrings
- Violates single-source-of-truth (DB is SSOT)
- Makes code harder to read
- LLMs love adding more metadata (slippery slope)

**Where metadata lives:**

| Data | Location | Why |
|------|----------|-----|
| Intent, behavior | Docstring | Humans read it |
| Action registry | PostgreSQL | SSOT for what exists |
| Pattern matching | Qdrant | Semantic search |
| Execution history | Activity log | What happened |
| IDs | Source code | Stable references |

---

## The Universal Contract

### ActionResult: The Brick Shape

Every atomic action returns the same shape:

```python
@dataclass
class ActionResult:
    """Universal contract - every brick has this shape"""

    action_id: str              # Identifies what action this was
    ok: bool                    # Binary: success or failure
    data: dict[str, Any]        # Action-specific details
    duration_sec: float = 0.0   # Performance tracking

    # Optional enrichment
    logs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
```

### Why This Works

**For Checks (read-only):**
```python
ActionResult(
    action_id="check.imports",
    ok=True,  # No violations
    data={"violations_count": 0, "files_scanned": 353}
)
```

**For Fixes (writes):**
```python
ActionResult(
    action_id="fix.headers",
    ok=True,  # Successfully fixed
    data={"violations_found": 1, "fixed_count": 1, "dry_run": False}
)
```

**For Sync (data operations):**
```python
ActionResult(
    action_id="sync.knowledge",
    ok=True,  # Sync succeeded
    data={"symbols_synced": 150, "symbols_added": 3}
)
```

**Same shape, different data, universal governance.**

### Function Signature Convention

```python
async def {action}_internal(write: bool = False) -> ActionResult:
    """
    One-line summary of what this brick does.

    Pattern: action_pattern | inspect_pattern | check_pattern
    Impact: read-only | write-metadata | write-code | write-data
    Policies: [list of constitutional policies this validates]
    """
```

**The `_internal` suffix signals:**
- This is an atomic action (a brick)
- Not meant to be called directly by users
- Part of a larger composition

---

## Discovery & Governance

### The Three-Layer System

```
┌─────────────────────────────────────┐
│ .intent/ (Mind - What Should Exist) │
│ - Patterns define rules             │
│ - Policies define constraints       │
│ - Constitution defines governance   │
└─────────────────────────────────────┘
          ↓ tells CORE what to build
┌─────────────────────────────────────┐
│ CORE (Orchestrator)                 │
│ - Reads .intent/                    │
│ - Asks LLMs to generate code        │
│ - Validates against patterns        │
└─────────────────────────────────────┘
          ↓ LLMs produce
┌─────────────────────────────────────┐
│ Code (Body - How It's Implemented)  │
│ - Small, focused functions          │
│ - Return ActionResult               │
│ - IDs for stability                 │
└─────────────────────────────────────┘
          ↓ registered in
┌─────────────────────────────────────┐
│ DB/Qdrant (Oversight - What Exists) │
│ - PostgreSQL: Action registry       │
│ - Qdrant: Semantic patterns         │
│ - Activity log: Execution history   │
└─────────────────────────────────────┘
```

### How Actions Are Discovered

**At Build Time (Constitutional Checker):**
```python
# Checker scans source files
for file in source_files:
    functions = parse_ast(file)
    for func in functions:
        if func.name.endswith('_internal'):
            if not returns_action_result(func):
                violations.append(f"{func.name} must return ActionResult")

            # Extract metadata from docstring
            metadata = parse_docstring(func)

            # Validate against DB
            if not db.action_exists(func.id):
                violations.append(f"{func.name} not registered in DB")
```

**At Runtime (Action Registry):**
```python
# System queries DB to find actions
actions = db.query("""
    SELECT action_id, pattern, impact, policies
    FROM action_registry
    WHERE pattern = 'action_pattern'
    AND impact = 'write-metadata'
""")

# Can discover and compose actions dynamically
for action in actions:
    if satisfies_requirements(action):
        result = await execute_action(action.action_id)
```

**Via Semantic Search (Qdrant):**
```python
# Find actions by natural language
results = qdrant.search(
    "actions that fix code style issues",
    collection="atomic_actions"
)

# Returns: fix.headers, fix.imports, fix.docstrings, ...
```

### Constitutional Validation Loop

```
1. Developer writes .intent/ (blueprint)
   ↓
2. CORE asks LLM to generate code
   ↓
3. LLM produces function
   ↓
4. Constitutional checker validates:
   - Returns ActionResult? ✓
   - Follows pattern? ✓
   - Registered in DB? ✓
   - Docstring complete? ✓
   ↓
5a. If valid → Canary test → Accept
5b. If invalid → Reject → Try again
```

**Key insight:** Validation happens at BUILD TIME, not via decorator inspection at runtime.

---

## Composition Over Complexity

### The Anti-Pattern: Kitchen Sink

```python
# ❌ WRONG - Does everything
async def dev_sync_all():
    """The kitchen sink"""
    # 1000 lines of everything
    assign_ids()
    fix_headers()
    format_code()
    run_linters()
    sync_database()
    update_vectors()
    generate_docs()
    # ... never stops growing
```

### The Right Pattern: Composition

```python
# ✅ RIGHT - Level 1: Atomic bricks
async def fix_ids_internal(write: bool) -> ActionResult:
    """Assign stable IDs. ONE thing."""
    # 40 lines, focused
    return ActionResult(...)

async def fix_headers_internal(write: bool) -> ActionResult:
    """Fix file headers. ONE thing."""
    # 35 lines, focused
    return ActionResult(...)

# ✅ RIGHT - Level 2: Composed workflow
async def dev_sync_internal(write: bool) -> ActionResult:
    """Orchestrates atomic actions"""
    results = []

    # Call bricks in sequence
    results.append(await fix_ids_internal(write))
    results.append(await fix_headers_internal(write))
    results.append(await check_lint_internal())

    # Aggregate results
    return ActionResult(
        action_id="dev.sync",
        ok=all(r.ok for r in results),
        data={
            "phases": len(results),
            "succeeded": sum(1 for r in results if r.ok),
            "details": [r.data for r in results]
        }
    )
```

### Composition Hierarchy

```
Atomic (bricks) → Composed (walls) → Workflows (rooms) → Features (house)

fix_ids_internal        dev_sync_internal       autonomous_dev
    ↓ builds                 ↓ builds                ↓ builds
fix_headers_internal    check_audit          self_improving_system
    ↓                        ↓                        ↓
check_lint_internal     coverage_repair           CORE
```

**Each level:**
- Composes the level below
- Returns ActionResult
- Has clear success/failure
- Can be tested independently

---

## Constitutional Enforcement

### What Gets Enforced

**1. Structural Compliance**

```yaml
# .intent/charter/patterns/atomic_actions.yaml
validation_rules:
  - rule: "action_must_return_result"
    check: "Function ending in _internal returns ActionResult"
    severity: "error"

  - rule: "action_must_be_focused"
    check: "Function is < 100 lines (not a kitchen sink)"
    severity: "warning"

  - rule: "action_must_be_registered"
    check: "Function exists in DB action_registry"
    severity: "error"
```

**2. Pattern Compliance**

```python
# Checker validates against command patterns
if func_name.startswith('check_'):
    assert 'write' not in func.parameters  # Check pattern: read-only

if func_name.startswith('fix_'):
    assert 'write' in func.parameters      # Action pattern: needs --write
    assert default_value_of('write') == False  # Must default to dry-run
```

**3. Registration in DB**

```sql
-- Every atomic action must be registered
CREATE TABLE action_registry (
    id UUID PRIMARY KEY,
    action_id TEXT UNIQUE NOT NULL,
    function_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    pattern TEXT NOT NULL,  -- inspect_pattern, action_pattern, etc.
    impact TEXT NOT NULL,   -- read-only, write-metadata, etc.
    policies TEXT[],        -- Constitutional policies validated
    created_at TIMESTAMP,
    last_verified TIMESTAMP
);
```

**4. Docstring Completeness**

```python
# Every _internal function must have complete docstring
required_sections = ['Pattern:', 'Impact:', 'Policies:']
for section in required_sections:
    if section not in func.docstring:
        violations.append(f"Missing {section} in docstring")
```

### Enforcement Points

**Build Time (CI/CD):**
```bash
# Must pass before merge
poetry run core-admin check atomic-actions
poetry run core-admin check patterns
```

**Canary Testing:**
```python
# Generated code tested in isolation
crate = create_crate(new_code)
canary_result = test_in_canary(crate)

if canary_result.constitutional_violations > 0:
    reject_crate("Constitutional violations found")
```

**Runtime (Activity Logging):**
```python
# All executions logged
with activity_run("dev.sync") as run:
    for action_id in workflow.actions:
        result = await execute_action(action_id)
        log_activity(run, action_id, result)
```

---

## Implementation Guide

### Step 1: Write in `.intent/`

```yaml
# .intent/charter/patterns/my_feature.yaml
feature: data_validation
atomic_actions:
  - action_id: "validate.data_format"
    purpose: "Check data follows schema"
    pattern: "check_pattern"
    impact: "read-only"

  - action_id: "fix.data_format"
    purpose: "Auto-correct schema violations"
    pattern: "action_pattern"
    impact: "write-data"
```

### Step 2: Generate Code (via CORE)

```bash
# CORE reads .intent/ and generates code
poetry run core-admin develop feature --from-file my_feature.yaml
```

### Step 3: LLM Produces Atomic Actions

```python
# Generated by LLM, validated by CORE
# ID: 8be64ae4-477d-4166-b7bf-bbb7a77a4c6c
async def validate_data_format_internal(file: Path) -> ActionResult:
    """
    Check data file follows expected schema.

    Pattern: check_pattern
    Impact: read-only
    Policies: data_governance
    """
    start = time.time()

    violations = []
    data = load_data(file)

    if not matches_schema(data):
        violations.append(f"{file}: Schema mismatch")

    return ActionResult(
        action_id="validate.data_format",
        ok=len(violations) == 0,
        data={
            "violations": violations,
            "files_checked": 1
        },
        duration_sec=time.time() - start
    )
```

### Step 4: Register in DB

```python
# Automatic registration during dev-sync
db.register_action(
    id="8be64ae4-477d-4166-b7bf-bbb7a77a4c6c",
    action_id="validate.data_format",
    function_name="validate_data_format_internal",
    file_path="src/features/validation/data.py",
    pattern="check_pattern",
    impact="read-only",
    policies=["data_governance"]
)
```

### Step 5: Validate & Accept

```bash
# Constitutional checker runs
poetry run core-admin check atomic-actions

# Output:
# ✅ validate_data_format_internal
#    - Returns ActionResult ✓
#    - Pattern: check_pattern ✓
#    - Registered in DB ✓
#    - Docstring complete ✓
```

---

## Migration Path

### Current State

```
Some functions return CommandResult ✓
Some functions return AuditCheckResult ✓
Some functions return dict ❌
Some functions return None ❌
Some functions print output ❌
```

### Target State

```
ALL _internal functions return ActionResult ✓
ALL registered in DB ✓
ALL validated by constitutional checker ✓
NO metadata pollution in decorators ✓
```

### Migration Steps

**Week 1: Create Infrastructure**
1. Create `ActionResult` dataclass
2. Create DB `action_registry` table
3. Create `check atomic-actions` command
4. Prove pattern with 2-3 actions

**Week 2-3: Migrate Actions**
1. Identify all `_internal` functions
2. Convert return types to `ActionResult`
3. Add docstring metadata (Pattern, Impact, Policies)
4. Register in DB
5. Validate with checker

**Week 4: Enforce**
1. Add to CI/CD pipeline
2. Block PRs with violations
3. Add to `dev-sync` workflow
4. Update documentation

---

## Summary

**Atomic actions are not about decorators or metadata pollution.**

They are about:

✅ **Structure** - Small, focused functions that do ONE thing
✅ **Contract** - ActionResult provides predictable shape
✅ **Composition** - Build UP through layers, not OUT through bloat
✅ **Discovery** - DB/Qdrant know what exists, enable search
✅ **Governance** - Constitutional validation at build time

**The brick layer philosophy:**
- You write `.intent/` (blueprints)
- CORE + LLMs build (bricks)
- DB/Qdrant validate (quality control)
- System composes (house)

**Source code stays pure. Governance stays constitutional. CORE stays self-improving.**

---

## References

- Constitutional Pattern: `.intent/charter/patterns/atomic_actions.yaml`
- Command Patterns: `.intent/charter/patterns/command_patterns.yaml`
- Code Purity Policy: `.intent/charter/policies/code_purity.yaml`
- Related: `docs/architecture/MIND_BODY_WILL.md`
