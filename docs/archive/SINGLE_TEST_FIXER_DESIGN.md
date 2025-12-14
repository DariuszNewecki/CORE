# Single Test Fixer - Design Document

## Purpose
Fix individual failing tests after initial test generation.

## Input
- Test file path
- Specific test function name (e.g., "test_get_logger_with_different_names")
- pytest error output
- Source code being tested (optional, for context)

## Output
- Fixed test code
- Status: "fixed" | "unfixable" | "error"

## Strategy

### 1. Parse pytest output to extract:
```python
{
    "test_name": "test_get_logger_with_different_names",
    "failure_type": "AssertionError",
    "expected": "''",
    "actual": "'root'",
    "line_number": 39,
    "full_traceback": "..."
}
```

### 2. Build focused prompt:
```
You are fixing a single failing test.

Test function: test_get_logger_with_different_names
Source file: tests/shared/test_logger.py

FAILURE:
AssertionError: assert 'root' == ''
  + root

The test code:
```python
def test_get_logger_with_different_names(self):
    test_names = ["", "test", "test.module", "123"]
    for name in test_names:
        logger = getLogger(name)
        assert logger.name == name  # ← FAILS HERE for empty string
```

The issue: When getLogger("") is called, it returns a logger named "root", not "".

Your task: Fix ONLY this test. Output the corrected test function.

Options:
1. Update assertion to match actual behavior
2. Skip empty string in test data
3. Add special case handling

Choose the fix that makes the test valid and meaningful.
```

### 3. Apply fix:
- Extract test function from file
- Replace with LLM's fixed version
- Run pytest on JUST that test
- Validate it passes

### 4. Iterate if needed (max 3 attempts per test)

## Implementation

```python
class SingleTestFixer:
    """
    Fixes individual failing tests using focused LLM prompts.
    """

    def __init__(
        self,
        cognitive_service: CognitiveService,
        max_attempts: int = 3
    ):
        self.cognitive = cognitive_service
        self.max_attempts = max_attempts

    async def fix_test(
        self,
        test_file: Path,
        test_name: str,
        failure_info: dict,
        source_file: Path | None = None,
    ) -> dict:
        """
        Fix a single failing test.

        Returns:
            {
                "status": "fixed" | "unfixable" | "error",
                "fixed_code": "...",
                "attempts": 2,
            }
        """
        pass
```

## Integration with Main Flow

```python
# In EnhancedTestGenerator.generate_test():

# STEP 5: Execute tests
execution_result = await self.executor.execute_test(...)

if execution_result.get("status") == "failed":
    # Parse failures
    failures = self._parse_test_failures(execution_result)

    # Try to fix each one
    fixer = SingleTestFixer(self.cognitive)
    fixed_count = 0

    for failure in failures:
        fix_result = await fixer.fix_test(
            test_file=test_file,
            test_name=failure["test_name"],
            failure_info=failure,
            source_file=module_path,
        )

        if fix_result["status"] == "fixed":
            fixed_count += 1

    # Re-run tests
    final_result = await self.executor.execute_test(...)

    if final_result.get("status") == "success":
        return {
            "status": "success",
            "message": f"All tests pass (fixed {fixed_count} failures)",
        }
```

## Advantages

1. **Higher Success Rate**: Focused context = better fixes
2. **Incremental Progress**: Each fix is isolated
3. **Debuggable**: Know exactly which fix worked/failed
4. **Composable**: Works with any test generator
5. **Autonomous**: No human intervention needed

## Key Insight

This matches CORE's philosophy:
- **Mind**: Constitutional rules about valid tests
- **Body**: Pure execution (pytest, code parsing)
- **Will**: Orchestration (decide which tests to fix, in what order)

The SingleTestFixer is a specialized agent in the Will layer.
