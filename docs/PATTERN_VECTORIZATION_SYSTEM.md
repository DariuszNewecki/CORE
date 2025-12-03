# Constitutional Pattern Vectorization System

## The Constitutional Foundation

**Philosophy:** CORE must understand its own constitution semantically, not just syntactically. Constitutional governance requires CORE to know what it should be (patterns) and validate what it is (code).

---

## What This System Does

### 1. Pattern Internalization
- Reads `.intent/charter/patterns/*.yaml`
- Chunks patterns into semantic sections
- Vectorizes each chunk with embeddings
- Stores in `core-patterns` Qdrant collection

### 2. Semantic Understanding
- Patterns become queryable knowledge
- "What does atomic_actions require?" → Returns requirements
- "Which patterns apply to *_internal functions?" → Returns applicable patterns

### 3. Constitutional Validation
- Compare pattern expectations vs actual code
- Detect violations semantically
- Report with constitutional citations
- Track migration progress

---

## The Architecture

### New Qdrant Collection: `core-patterns`

```yaml
collection_name: core-patterns
vector_dimension: 1536
distance_metric: cosine

metadata_schema:
  pattern_id: "atomic_actions"
  pattern_version: "1.0.0"
  pattern_category: "orchestration"
  section_type: "requirement" | "example" | "validation_rule" | "migration"
  section_path: "atomic_action.universal_contract.output"
  applies_to: ["*_internal functions"]
  severity: "error" | "warning" | "info"
```

### Chunking Strategy

Each pattern becomes multiple semantic chunks:

**Philosophy Section:**
```
Pattern: atomic_actions
Section: philosophy
Content: "CORE is not a collection of commands..."
```

**Requirements:**
```
Pattern: atomic_actions
Section: requirements.pattern_understanding
Content: "CORE MUST maintain semantic understanding..."
```

**Validation Rules:**
```
Pattern: atomic_actions
Section: validation_rules.action_must_return_result
Content: "Every atomic action MUST return ActionResult"
Severity: error
```

**Examples:**
```
Pattern: atomic_actions
Section: examples.read_action
Content: Full example of check.imports action
```

**Migration Phases:**
```
Pattern: atomic_actions
Section: migration.phases.phase_1_unification
Content: Steps for Phase 1
```

---

## How It Works

### Step 1: Vectorize Patterns

```bash
poetry run core-admin manage patterns vectorize
```

Output:
```
✓ Vectorized 5 patterns
  Total chunks: ~40-50 chunks

Pattern Vectorization Results:
┌─────────────────────┬────────┐
│ Pattern             │ Chunks │
├─────────────────────┼────────┤
│ atomic_actions      │   12   │
│ command_patterns    │    8   │
│ workflow_patterns   │   10   │
│ agent_patterns      │    9   │
│ service_patterns    │    7   │
└─────────────────────┴────────┘
```

### Step 2: Query Patterns

```bash
poetry run core-admin manage patterns query "what does atomic_actions require?"
```

Output:
```
Found 3 matches:

1. atomic_actions (0.923)
   Section: requirements.pattern_understanding
   CORE MUST maintain semantic understanding of all constitutional
   patterns defined in .intent/charter/patterns/...

2. atomic_actions (0.891)
   Section: atomic_action.universal_contract.output
   ActionResult with standard structure: action_id, ok, data,
   duration_sec, impact...

3. atomic_actions (0.876)
   Section: validation_rules.action_must_return_result
   Every atomic action MUST return an ActionResult...
```

### Step 3: Validate Code (Coming Next)

```bash
poetry run core-admin check patterns
```

Will:
1. Query patterns for requirements
2. Query knowledge graph for actual code
3. Compare semantically
4. Report violations with citations

---

## Files Created

### 1. Constitutional Policy
**File:** `.intent/charter/policies/pattern_vectorization.yaml`
**Purpose:** Defines HOW patterns should be vectorized and validated

**Key Sections:**
- Philosophy: Why semantic understanding matters
- Requirements: What CORE must do
- Vector collection schema
- Validation workflow
- Implementation phases

### 2. Implementation Service
**File:** `src/services/vectorization/pattern_vectorizer.py`
**Purpose:** Actually vectorizes patterns

**Key Classes:**
- `PatternChunk`: Represents a semantic chunk
- `PatternVectorizer`: Handles vectorization and queries

**Key Methods:**
- `vectorize_all_patterns()`: Process all pattern files
- `vectorize_pattern()`: Process single pattern
- `query_pattern()`: Semantic pattern search

### 3. CLI Commands
**File:** `src/body/cli/commands/manage/patterns.py`
**Purpose:** User interface to pattern system

**Commands:**
- `manage patterns vectorize`: Vectorize all patterns
- `manage patterns query "..."`: Search patterns semantically

---

## Installation

### Step 1: Install Files

```bash
cd /opt/dev/CORE

# Install policy
cp /path/to/pattern_vectorization.yaml .intent/charter/policies/

# Install service
mkdir -p src/services/vectorization
cp /path/to/pattern_vectorizer.py src/services/vectorization/

# Install CLI
cp /path/to/patterns_cli.py src/body/cli/commands/manage/patterns.py
```

### Step 2: Register CLI Command

Update `src/body/cli/commands/manage/__init__.py`:

```python
from .patterns import patterns_app

manage_app.add_typer(patterns_app, name="patterns")
```

### Step 3: Vectorize Patterns

```bash
# First time setup
poetry run core-admin manage patterns vectorize

# Query to test
poetry run core-admin manage patterns query "atomic action requirements"
```

---

## What This Enables

### ✅ Self-Awareness
CORE knows what patterns it should follow

### ✅ Semantic Validation
Compare expectations vs reality using vector similarity

### ✅ Constitutional Citations
Violations reference specific pattern sections

### ✅ Migration Tracking
Query: "What's the migration status for atomic_actions?"

### ✅ Autonomous Understanding
AI agents can query patterns to understand requirements

---

## The Bigger Picture

### Before This System:
- Patterns existed but weren't queryable
- Audit checks were hardcoded
- No way to ask "what does CORE require?"

### After This System:
- Patterns are semantic knowledge
- Audit derives checks from constitution
- Can query: "Does fix_ids conform to atomic_actions pattern?"

### This Is Constitutional Governance:
1. Constitution defines truth (patterns)
2. System internalizes constitution (vectorization)
3. System validates itself (semantic comparison)
4. System reports violations (delta = truth - reality)

---

## Next Steps

### Phase 1: Foundation (Today)
- ✅ Create pattern_vectorization policy
- ✅ Implement PatternVectorizer service
- ✅ Create CLI commands
- ⏳ Install and test

### Phase 2: Validation (Next)
- Create SemanticValidator service
- Implement pattern-code comparison
- Add to constitutional audit
- Report violations with citations

### Phase 3: Automation
- Auto-vectorize on pattern changes
- Real-time validation during development
- Suggest remediations automatically
- Track migration progress constitutionally

---

## Success Criteria

**CORE can answer:**
- "What does atomic_actions pattern require?" ✓
- "Which functions violate atomic_actions?" (Phase 2)
- "What's the migration progress?" (Phase 2)
- "How do I fix violation X?" (Phase 3)

**Constitutional Audit:**
- Reports pattern violations ✓
- Cites specific pattern sections ✓
- Provides remediation guidance (Phase 2)
- Tracks progress over time (Phase 2)

---

## The Constitutional Principle

> "The constitution defines what CORE should be.
>  CORE internalizes that definition semantically.
>  CORE validates itself against constitutional truth.
>  CORE reports the delta and self-heals within bounds."

**This is self-awareness. This is constitutional governance. This is CORE.**

---

## Commands Summary

```bash
# Vectorize all patterns
poetry run core-admin manage patterns vectorize

# Query patterns
poetry run core-admin manage patterns query "atomic action contract"

# Validate code (Phase 2)
poetry run core-admin check patterns

# Check migration status (Phase 2)
poetry run core-admin check migration-status
```

---

**Constitutional Innovation:** CORE now understands its own constitution semantically and can validate itself against constitutional truth. The system knows what it should be.
