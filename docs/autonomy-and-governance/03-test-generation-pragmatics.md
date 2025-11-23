# Pragmatic Autonomous Test Generation for CORE

**Philosophy:** "Any test that passes and doesn't break CI is a win."

---

## 1. The Simple Solution

### Current Problem

CORE previously tried to test **entire files** at once, resulting in ~30% valid outputs. This caused whole results to be rejected.

### Better Approach

Test **one symbol at a time** (one function/class).
Accept partial results.
Accumulate tests over time.

This dramatically increases success rate and coverage.

---

## 2. Symbol-by-Symbol Test Generation

### SimpleTestGenerator

A minimal test generator that:

* Extracts *one* symbol from a Python file
* Asks the LLM to produce *one* pytest function
* Validates it by actually running pytest
* Accepts it only if it passes

It never retries. It never blocks. It celebrates successful tests.

### AccumulativeTestService

A wrapper that:

* Iterates through all symbols in a file
* Attempts generation for each
* Keeps only the passing tests
* Writes them into a consolidated `tests/` file

Over days/weeks, this leads to hundreds of generated tests.

---

## 3. CLI Command: `coverage accumulate`

Adds a new CLI workflow:

```
poetry run core-admin coverage accumulate <path-to-source-file>
```

This processes one file, testing each symbol individually.

---

## 4. Expected Output Example

```
📝 Accumulating tests for src/core/prompt_pipeline.py
   Found 8 symbols
Generating tests... ███████████████████████████████ 100%
   ✅ process
   ❌ _inject_context
   ✅ _inject_includes
   ❌ _inject_analysis
   ✅ _inject_manifest
   ❌ _load_manifest
   ✅ get_repo_root
   ❌ _extract_json

✅ Generated 4/8 tests
   Saved to: tests/core/prompt_pipeline/test_prompt_pipeline.py
```

---

## 5. Why This Works

### ✔ Higher Success Rate

LLMs perform better on **small, isolated tasks**.

### ✔ Fail-Fast Philosophy

If a symbol fails, skip it immediately.

### ✔ Accumulation Over Time

Repeat execution gradually builds comprehensive coverage.

### ✔ Zero CI Risk

Only tests that *run successfully* are accepted.

---

## 6. Expected Impact on Coverage

| Scenario    | Symbols | Success Rate | Tests Added | Coverage Gain |
| ----------- | ------- | ------------ | ----------- | ------------- |
| Pessimistic | 1000    | 40%          | 400         | ~15%          |
| Realistic   | 1000    | 50%          | 500         | ~20–25%       |
| Optimistic  | 1000    | 60%          | 600         | ~25–30%       |

All results are positive.

---

## 7. Constitutional Alignment

This approach is fully compatible with CORE principles:

### safe_by_default

* Only tests that run safely are added.

### evolvable_structure

* Grows gradually and iteratively.

### pragmatic_autonomy

* Values incremental success over perfection.

### Proposed Policy Addition

```yaml
# .intent/charter/policies/governance/quality_assurance_policy.yaml

test_generation:
  mode: accumulative
  philosophy: >
    We value incremental progress. Any test that CORE can successfully
    generate and validate is better than no test. We do not require
    comprehensive coverage from autonomous generation.
  success_criteria:
    - test_compiles: true
    - test_runs_without_error: true
    - test_does_not_break_ci: true
```

---

## 8. Implementation Summary

Files to add:

* `src/features/self_healing/simple_test_generator.py`
* `src/features/self_healing/accumulative_test_service.py`
* CLI extension in `src/cli/commands/coverage.py`

---

## 9. Usage Examples

### Generate tests for a single file

```
poetry run core-admin coverage accumulate src/shared/logger.py
```

### Process many files in batch

```
for file in $(find src -name "*.py"); do
    poetry run core-admin coverage accumulate "$file"
done
```

---

## 10. Bottom Line

* **Lower the bar.**
* **Increase throughput.**
* **Celebrate every passing test.**

This is the practical, realistic path to autonomous test coverage growth in CORE.
