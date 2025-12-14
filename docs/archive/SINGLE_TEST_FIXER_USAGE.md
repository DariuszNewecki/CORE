# Example: How to use SingleTestFixer

## Standalone Usage

```python
from pathlib import Path
from will.orchestration.cognitive_service import CognitiveService
from features.self_healing.test_generation.single_test_fixer import (
    SingleTestFixer,
    TestFailureParser
)

# Initialize
cognitive = CognitiveService(...)
fixer = SingleTestFixer(cognitive, max_attempts=3)

# Parse pytest output to get failures
pytest_output = """
FAILED tests/shared/test_logger.py::TestGetLogger::test_get_logger_with_different_names - AssertionError: assert 'root' == ''
"""

parser = TestFailureParser()
failures = parser.parse_failures(pytest_output)

# Fix each failing test
for failure in failures:
    result = await fixer.fix_test(
        test_file=Path("tests/shared/test_logger.py"),
        test_name=failure["test_name"],
        failure_info=failure,
        source_file=Path("src/shared/logger.py"),
    )

    if result["status"] == "fixed":
        print(f"✓ Fixed {failure['test_name']} in {result['attempts']} attempts")
    else:
        print(f"✗ Could not fix {failure['test_name']}: {result.get('final_error')}")
```

## Integrated Usage (Automatic)

The SingleTestFixer is now automatically integrated into `EnhancedTestGenerator`.

When tests are generated and some fail:
1. Generator creates tests (e.g., 13/17 pass)
2. Automatic syntax repairs run
3. **NEW**: SingleTestFixer attempts to fix each failing test
4. Re-runs tests after fixes
5. Reports final status

### Flow Example:

```
Initial generation: 13/17 tests pass (76%)
  ↓
Identifying failures: 4 tests failed
  ↓
Fixing test 1: test_get_logger_with_different_names
  → Attempt 1: Success! ✓
  ↓
Fixing test 2: test_reconfigure_log_level_case_insensitive
  → Attempt 1: Success! ✓
  ↓
Fixing test 3: test_auto_configure_called_on_import
  → Attempt 1: Failed
  → Attempt 2: Success! ✓
  ↓
Fixing test 4: test_custom_log_format_from_env
  → Attempt 1: Failed
  → Attempt 2: Failed
  → Attempt 3: Failed
  → Unfixable ✗
  ↓
Re-running tests: 16/17 pass (94%)
  ↓
Final result: "Tests generated, fixed 3 failures, but 1 still fails"
```

## Configuration

Control the behavior via EnhancedTestGenerator init:

```python
generator = EnhancedTestGenerator(
    cognitive_service=cognitive,
    auditor_context=auditor,
    use_iterative_fixing=True,  # Enable test fixing
    max_fix_attempts=3,          # Max attempts per test
)
```

## Limits

- **Max 10 failures**: Only attempts to fix if ≤ 10 tests fail
- **Max 3 attempts per test**: Gives up after 3 tries
- **Syntax validation**: Fixed code must be valid Python

## Expected Improvement

Typical results:
- **Before**: 70-80% tests pass on first generation
- **After SingleTestFixer**: 90-95% tests pass
- **Remaining failures**: Usually unfixable logic issues, flag for human review
