# CORE Restructure Plan: Mind-Body-Will Architecture (CORRECTED)

## What You Actually Have

```
src/
├── api/              # FastAPI routes
├── cli/              # CLI commands
├── core/             # Agents + orchestration (currently mixed)
├── features/         # Business features
├── services/         # Infrastructure services
└── shared/           # Shared utilities
```

## Where Things Should Go

### Mind (Constitutional Enforcement)
**Currently in:** `src/features/governance/`
**Move to:** `src/mind/governance/`

Files to move:
- Everything in `src/features/governance/` that enforces constitutional rules
- The constitutional auditor (likely in `src/features/governance/`)

### Body (Execution Without Decisions)
**Keep as-is, just organize:**
- `src/services/` - Infrastructure (DB, LLM clients, etc.)
- `src/features/` - Business capabilities (after removing governance)
- `src/cli/` - CLI commands

### Will (AI Orchestration & Decisions)
**Currently in:** `src/core/agents/`
**Move to:** `src/will/agents/`

Files to move:
- Everything in `src/core/agents/`
- Any orchestration logic in `src/core/`

---

## Step-by-Step Migration

### Phase 1: Identify Files

Run this to see what's actually in each directory:

```bash
# Find governance files
find src/features/governance -name "*.py" -type f

# Find agent files
find src/core/agents -name "*.py" -type f

# Find core files that aren't agents
find src/core -name "*.py" -type f -not -path "*/agents/*"
```

### Phase 2: Create New Structure

```bash
# Create Mind structure
mkdir -p src/mind/governance

# Create Will structure
mkdir -p src/will/agents
mkdir -p src/will/orchestration

# Add __init__.py files
touch src/mind/__init__.py
touch src/mind/governance/__init__.py
touch src/will/__init__.py
touch src/will/agents/__init__.py
touch src/will/orchestration/__init__.py
```

### Phase 3: Move Mind Files

**Move governance features to Mind:**

```bash
# FIRST: See what's there
ls -la src/features/governance/

# Then move the files
# Example (adjust based on what you find):
git mv src/features/governance/checks src/mind/governance/
git mv src/features/governance/auditor.py src/mind/governance/
git mv src/features/governance/policy_loader.py src/mind/governance/

# Keep the __init__ for now
# git mv src/features/governance/__init__.py src/mind/governance/
```

### Phase 4: Move Will Files

**Move agents from core to will:**

```bash
# Move all agents
git mv src/core/agents/* src/will/agents/

# Move orchestration if it exists
# (Check first what orchestration files exist in src/core/)
```

### Phase 5: Reorganize Body

**Classify remaining src/core/ files:**

After moving agents, you'll have files left in `src/core/`. Classify each:

- **Decision-making?** → Move to `src/will/orchestration/`
- **Pure execution?** → Move to `src/services/` or `src/features/`

```bash
# Example - if cognitive_service makes decisions:
git mv src/core/cognitive_service.py src/will/orchestration/

# Example - if it's pure execution:
git mv src/core/some_service.py src/services/
```

### Phase 6: Fix Imports

**Update imports in moved files:**

```bash
# Find all imports that need updating
grep -r "from src.features.governance" src/
grep -r "from src.core.agents" src/
grep -r "from src.core" src/ | grep -v ".pyc"
```

**Common replacements:**
- `from src.features.governance` → `from src.mind.governance`
- `from src.core.agents` → `from src.will.agents`
- Remaining `from src.core` → Case by case based on where you moved files

### Phase 7: Update Tests

```bash
# Create test structure
mkdir -p tests/mind/governance
mkdir -p tests/will/agents

# Move governance tests
git mv tests/features/test_*governance* tests/mind/governance/
git mv tests/features/test_auditor* tests/mind/governance/

# Move agent tests
find tests -name "test_*agent*.py" -exec git mv {} tests/will/agents/ \;
```

### Phase 8: Clean Up Empty Directories

```bash
# After moving everything, remove empty dirs
rmdir src/core/agents  # If empty
rmdir src/core         # If empty after reclassifying files
```

---

## Quick Decision Tree

For each file in `src/core/`:

**Does it make decisions or orchestrate?**
- Yes → `src/will/`
- No → Continue

**Does it enforce constitutional rules?**
- Yes → `src/mind/`
- No → Continue

**Is it infrastructure/utility?**
- Yes → `src/services/` or `src/shared/`
- No → `src/features/` (domain logic)

---

## Verification Commands

After each phase:

```bash
# 1. Check syntax
python -m py_compile src/**/*.py

# 2. Run tests
poetry run pytest tests/ -v

# 3. Try importing
poetry run python -c "from src.mind import *; from src.will import *"

# 4. Run CLI
poetry run core-admin system check
```

---

## What To Do Right Now

Since you're at Step 2.1 and hit an issue:

```bash
# STOP - Let's see what you actually have
cd /path/to/CORE

# 1. What governance files exist?
find src -path "*/governance/*" -name "*.py"

# 2. What's in features?
ls -R src/features/

# 3. Where is the auditor?
find src -name "*audit*.py" | grep -v test | grep -v __pycache__

# Show me the output and I'll give you exact commands
```

---

## Simplified First Step

**Just do Mind first, nothing else:**

1. `mkdir -p src/mind/governance`
2. `touch src/mind/__init__.py src/mind/governance/__init__.py`
3. Find where governance files are: `ls -la src/features/governance/`
4. Move them: `git mv src/features/governance/*.py src/mind/governance/`
5. Fix imports in those files
6. Test: `poetry run pytest tests/`

**Then stop and show me what broke.** We'll fix imports before moving to Body/Will.

---

## Key Insight

You don't have `src/governance/` - you have `src/features/governance/`.

The governance features ARE your Mind. Move those first, fix imports, test. Then tackle agents (Will).

One layer at a time.
