#!/bin/bash
set -e

echo "🤖 ============================================"
echo "🤖 CORE AUTONOMOUS TESTING SYSTEM v1.0"
echo "🤖 ============================================"
echo ""

# Setup work directories
WORK_DIR="work/testing"
STRATEGY_DIR="$WORK_DIR/strategy"
GOALS_DIR="$WORK_DIR/goals"
LOGS_DIR="$WORK_DIR/logs"
REPORTS_DIR="$WORK_DIR/reports"

mkdir -p "$STRATEGY_DIR" "$GOALS_DIR" "$LOGS_DIR" "$REPORTS_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOGS_DIR/run_${TIMESTAMP}.log"

echo "📁 Working directory: $WORK_DIR"
echo "📝 Log file: $LOG_FILE"
echo ""

COVERAGE_TARGET=40
MAX_ITERATIONS=10
ITERATION=0

# Redirect all output to log file AND terminal
exec > >(tee -a "$LOG_FILE")
exec 2>&1

echo "📊 Current Coverage:"
poetry run pytest --cov=src --cov-report=term | grep "TOTAL"
echo ""

# Phase 1: Strategic Analysis
echo "🧠 Phase 1: Analyzing codebase and generating strategy..."
if poetry run core-admin run develop "Analyze the current test coverage by examining the source code structure and existing tests. Create a prioritized testing strategy in work/testing/strategy/test_plan.md that includes:
1. Current overall coverage percentage
2. Top 10 modules needing tests (prioritize by: number of imports/dependencies, current coverage %, code complexity, criticality to system)
3. For each module: current coverage %, target coverage %, reason for priority, estimated complexity
4. Dependency order (test foundational modules before modules that depend on them)
Use AST analysis of imports and file sizes as indicators of importance."; then
  echo "✅ Strategy generation completed"
else
  echo "⚠️ Strategy generation had issues, checking if file exists..."
fi

if [ ! -f "$STRATEGY_DIR/test_plan.md" ]; then
  echo "❌ Strategy file not created at $STRATEGY_DIR/test_plan.md"
  echo "Creating directory structure and retrying..."
  mkdir -p "$STRATEGY_DIR"

  # Manual fallback strategy
  cat > "$STRATEGY_DIR/test_plan.md" << 'STRATEGY'
# Test Coverage Strategy

## Current Status
Coverage: 22%

## Priority Modules (Top 10)

1. **src/core/prompt_pipeline.py** (41% → 80%)
   - High usage by all agents
   - Core functionality for LLM interaction

2. **src/core/validation_pipeline.py** (36% → 75%)
   - Critical for code quality
   - Used before any code commit

3. **src/core/python_validator.py** (31% → 70%)
   - Core validation component

4. **src/core/actions/file_actions.py** (34% → 75%)
   - File operations used everywhere

5. **src/core/actions/code_actions.py** (24% → 70%)
   - Code generation actions

STRATEGY

  echo "✅ Created fallback strategy"
fi

echo "✅ Strategy: $STRATEGY_DIR/test_plan.md"
echo ""

# Phase 2: Generate Goals
echo "📝 Phase 2: Converting strategy into executable goals..."
if poetry run core-admin run develop "Read work/testing/strategy/test_plan.md and convert the top 5 priorities into work/testing/goals/test_goals.json with this EXACT JSON format (no markdown, pure JSON):
{
  \"goals\": [
    {
      \"module\": \"src/core/prompt_pipeline.py\",
      \"test_file\": \"tests/unit/test_prompt_pipeline.py\",
      \"priority\": 1,
      \"current_coverage\": 41,
      \"target_coverage\": 80,
      \"goal\": \"Create comprehensive unit tests for PromptPipeline class. Test directive processing, file operations, error handling. Use mocks for file system. Target 80%+ coverage.\"
    }
  ]
}"; then
  echo "✅ Goals generation completed"
else
  echo "⚠️ Goals generation had issues..."
fi

if [ ! -f "$GOALS_DIR/test_goals.json" ]; then
  echo "❌ Goals file not created. Creating fallback..."

  cat > "$GOALS_DIR/test_goals.json" << 'GOALS'
{
  "goals": [
    {
      "module": "src/core/prompt_pipeline.py",
      "test_file": "tests/unit/test_prompt_pipeline.py",
      "priority": 1,
      "current_coverage": 41,
      "target_coverage": 80,
      "goal": "Create comprehensive unit tests for tests/unit/test_prompt_pipeline.py covering PromptPipeline class methods, directive processing, file reading, and error handling. Use pytest and mocks."
    }
  ]
}
GOALS

  echo "✅ Created fallback goals"
fi

GOAL_COUNT=$(python3 -c "import json; print(len(json.load(open('$GOALS_DIR/test_goals.json'))['goals']))" 2>/dev/null || echo "1")
echo "📋 Have $GOAL_COUNT test goals"
echo ""

# Phase 3: Execute
echo "🔨 Phase 3: Executing test generation..."

while [ $ITERATION -lt $MAX_ITERATIONS ]; do
  ITERATION=$((ITERATION + 1))

  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "📍 Iteration $ITERATION of $MAX_ITERATIONS"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  # Get next goal
  NEXT_GOAL=$(python3 << 'PYTHON'
import json
import sys

try:
    with open('work/testing/goals/test_goals.json', 'r') as f:
        data = json.load(f)

    if not data.get('goals') or len(data['goals']) == 0:
        print("NONE")
        sys.exit(0)

    goal = data['goals'][0]
    print(f"{goal['module']}:::{goal['test_file']}:::{goal['goal']}")
except Exception as e:
    print("ERROR")
    sys.exit(1)
PYTHON
)

  if [ "$NEXT_GOAL" = "NONE" ]; then
    echo "✅ All goals completed!"
    break
  fi

  if [ "$NEXT_GOAL" = "ERROR" ]; then
    echo "❌ Error reading goals"
    break
  fi

  MODULE=$(echo "$NEXT_GOAL" | cut -d':::' -f1)
  TEST_FILE=$(echo "$NEXT_GOAL" | cut -d':::' -f2)
  GOAL=$(echo "$NEXT_GOAL" | cut -d':::' -f3-)

  echo "🎯 Target: $MODULE"
  echo "📝 Test File: $TEST_FILE"
  echo ""

  echo "⚙️  Generating tests..."
  poetry run core-admin run develop "$GOAL" || echo "⚠️ Development step had issues"

  if [ -f "$TEST_FILE" ]; then
    echo ""
    echo "🧪 Running tests..."
    poetry run pytest "$TEST_FILE" -v || echo "⚠️ Tests failed"
  fi

  # Remove completed goal
  python3 << 'PYTHON'
import json
with open('work/testing/goals/test_goals.json', 'r') as f:
    data = json.load(f)
if data.get('goals'):
    data['goals'].pop(0)
with open('work/testing/goals/test_goals.json', 'w') as f:
    json.dump(data, f, indent=2)
PYTHON

  echo ""
  echo "💤 Cooling down (10s)..."
  sleep 10
done

echo ""
echo "🎊 Run Complete!"
poetry run pytest --cov=src --cov-report=term | grep TOTAL
