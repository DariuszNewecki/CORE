# .intent/charter/patterns/README.md
# CORE Design Patterns

## Overview

This directory defines the canonical design patterns used throughout CORE. Every component MUST follow one of these patterns to ensure consistency, maintainability, and constitutional compliance.

## Pattern Categories

### 1. Command Patterns (`command_patterns.yaml`)
Defines how CLI commands should be structured and behave.

**Patterns:**
- `inspect_pattern` - Read-only queries (safe, idempotent)
- `action_pattern` - State-modifying operations (dry-run first, --write to execute)
- `check_pattern` - Validation operations (pass/fail with actionable feedback)
- `run_pattern` - Autonomous operations (respects autonomy lanes)
- `manage_pattern` - Administrative operations (infrastructure management)

**Usage:** Every CLI command in `src/body/cli/` MUST follow one of these patterns.

### 2. Service Patterns (`service_patterns.yaml`)
Defines how infrastructure services should be architected.

**Patterns:**
- `stateful_service` - Long-lived stateful resources (DB, Qdrant, LLM clients)
- `stateless_transformer` - Pure data transformations (validators, parsers)
- `repository_pattern` - Data access abstraction (domain objects, not raw SQL)
- `facade_pattern` - Simplified interface to complex subsystems
- `observer_pattern` - Event-driven decoupling

**Usage:** Every service in `src/services/` MUST follow one of these patterns.

### 3. Agent Patterns (`agent_patterns.yaml`)
Defines how autonomous agents should be structured.

**Patterns:**
- `cognitive_agent` - LLM-powered reasoning (prompts, context, decisions)
- `orchestrator_agent` - Multi-agent coordination (planning, execution, validation)
- `validator_agent` - Quality and compliance verification
- `learning_agent` - Performance improvement through experience

**Usage:** Every agent in `src/will/agents/` MUST follow one of these patterns.

### 4. Workflow Patterns (`workflow_patterns.yaml`)
Defines how multi-step operations should be orchestrated.

**Patterns:**
- `linear_workflow` - Sequential steps (fail-fast)
- `dag_workflow` - Dependency-based parallelization
- `saga_workflow` - Transactional with rollback
- `event_driven_workflow` - Reactive to triggers
- `autonomous_workflow` - Self-improving through feedback

**Usage:** Every Makefile target and multi-step operation MUST follow one of these patterns.

## Pattern Compliance

### Declaration

Every component MUST declare its pattern in the docstring:

```python
"""
Module description here.

Pattern: cognitive_agent
See: .intent/charter/patterns/agent_patterns.yaml#cognitive_agent
"""
```

### Validation

Pattern compliance is enforced through:

1. **Manual code review** - Pattern violations block PR merge
2. **Automated checks** - `core-admin check patterns` validates implementation
3. **CI pipeline** - Pattern checks run on every commit
4. **Dev sync** - `make dev-sync` includes pattern validation

### Checker Tool

```bash
# Check all code against patterns
core-admin check patterns

# Check specific category
core-admin check patterns --category agents

# Auto-fix where possible
core-admin fix patterns --write

# Show pattern violations report
core-admin inspect patterns --violations-only
```

## Adding New Patterns

New patterns require **constitutional amendment** because they affect system-wide architecture.

### Process

1. **Proposal** - Create `cr-YYYYMMDD-pattern-name.yaml` proposal
2. **Justification** - Explain why existing patterns don't suffice
3. **Specification** - Define pattern completely (guarantees, requirements, examples)
4. **Review** - Get quorum approval from maintainers
5. **Ratification** - Merge after constitutional audit passes
6. **Migration** - Update existing code to follow new pattern

### Template

```yaml
- pattern_id: "new_pattern_name"
  type: "category"
  purpose: "One-line description"

  applies_to:
    - "Specific use cases"

  characteristics:
    - "Key trait 1"
    - "Key trait 2"

  implementation_requirements:
    structure: "How to organize code"
    guarantees: "What this pattern promises"
    anti_patterns: "What to avoid"

  example_implementation: |
    # Code skeleton showing pattern
```

## Pattern Evolution

Patterns evolve through:

1. **Usage feedback** - Developers report pain points
2. **Analysis** - Review violations and workarounds
3. **Refinement** - Update pattern specification
4. **Migration** - Update existing code
5. **Validation** - Verify improvements

This is tracked in:
- Pattern version numbers (semantic versioning)
- Migration guides in each pattern file
- Changelog in this README

## Pattern Checker Implementation

The pattern checker (`core-admin check patterns`) validates:

### For Command Patterns
- [ ] Has `--dry-run` or `--write` flag (action pattern)
- [ ] Returns appropriate exit codes
- [ ] Follows naming convention (`inspect <noun>`, `<verb> <noun>`)
- [ ] Has pattern declaration in docstring

### For Service Patterns
- [ ] Uses dependency injection (not global state)
- [ ] Implements initialization/shutdown lifecycle
- [ ] Has appropriate error handling
- [ ] Follows naming convention (e.g., `*Service`, `*Repository`)

### For Agent Patterns
- [ ] Accepts ContextPackage
- [ ] Returns structured decision
- [ ] Integrates constitutional guard
- [ ] Implements prompt management

### For Workflow Patterns
- [ ] Declares steps explicitly
- [ ] Implements error handling
- [ ] Provides progress indication
- [ ] Supports idempotency

## Benefits of Pattern Compliance

### Consistency
- Code looks familiar across the system
- Reduces cognitive load for developers
- Makes code reviews easier

### Safety
- Known error handling strategies
- Validated approaches to common problems
- Constitutional compliance built-in

### Maintainability
- Easier to refactor (pattern stays, implementation changes)
- Clear boundaries between components
- Documented architectural decisions

### Autonomy
- Patterns enable AI agents to understand code structure
- Consistent patterns improve placement accuracy
- Self-healing can fix pattern violations automatically

## Anti-Patterns

### Forbidden Practices

❌ **Pattern mixing** - Don't combine multiple patterns in one component
```python
# Bad: Inspect command that also modifies state
def inspect_and_fix_headers():
    show_violations()  # inspect pattern
    fix_violations()   # action pattern - WRONG!
```

✅ **Separate concerns** - Use composition instead
```python
def inspect_headers():
    return show_violations()  # inspect pattern only

def fix_headers():
    fix_violations()  # action pattern only
```

❌ **Pattern avoidance** - Don't work around patterns
```python
# Bad: Action that defaults to --write
def fix_something(write: bool = True):  # WRONG!
```

✅ **Follow the pattern**
```python
def fix_something(write: bool = False):  # dry-run by default
```

❌ **Hidden side effects** - Don't violate pattern guarantees
```python
# Bad: inspect command that caches to disk
def inspect_state():
    state = get_state()
    cache_to_disk(state)  # WRONG! Not read-only
    return state
```

✅ **Honor guarantees**
```python
def inspect_state(save: Optional[Path] = None):
    state = get_state()
    if save:  # Explicit opt-in
        save_to_file(state, save)
    return state
```

## Pattern Migration Status

Track migration progress here:

### Command Patterns
- [ ] Audit all CLI commands
- [ ] Tag with pattern IDs
- [ ] Fix violations
- [ ] Add automated checks

### Service Patterns
- [ ] Audit all services
- [ ] Remove global state
- [ ] Implement dependency injection
- [ ] Add lifecycle methods

### Agent Patterns
- [ ] Standardize ContextPackage usage
- [ ] Move prompts to `.intent/mind/prompts/`
- [ ] Add constitutional guards
- [ ] Implement structured decisions

### Workflow Patterns
- [ ] Add activity tracking
- [ ] Standardize error handling
- [ ] Add progress indication
- [ ] Document workflow composition

## Resources

- **Pattern specifications**: `*.yaml` files in this directory
- **Implementation examples**: See `examples/` subdirectory (TODO)
- **Migration guides**: In each pattern YAML file
- **Pattern checker**: `src/body/cli/commands/check_patterns.py` (TODO)

## Questions?

Pattern-related questions should be raised as GitHub issues with the `pattern` label.

For constitutional amendments to patterns, create a formal proposal in `.intent/charter/proposals/`.
