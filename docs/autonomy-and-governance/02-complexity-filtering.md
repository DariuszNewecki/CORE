# Complexity Filtering - Focus on Easy Wins

## What This Does

Analyzes files BEFORE attempting tests. Skips files that are too complex.

## Three Modes

```python
max_complexity="SIMPLE"     # Only trivial functions (nightly mode)
max_complexity="MODERATE"   # Balanced (default)
max_complexity="COMPLEX"    # Try everything (aggressive)
```

## How It Works

Uses `test_target_analyzer.py` to check each function:
- **SIMPLE**: No branches, no external deps
- **MODERATE**: Some if/else, basic logic
- **COMPLEX**: Many branches, nested loops, external deps

If file has ANY targets matching your threshold, it attempts generation.

## Integration

Copy these files:
```bash
cp complexity_filter.py src/features/self_healing/
cp test_generator_v2.py src/features/self_healing/      # Updated
cp single_file_remediation_v2.py src/features/self_healing/  # Updated
cp coverage_remediation_service_v2.py src/features/self_healing/  # Updated
```

## Usage

### CLI (Future)
```bash
# Only simple files
core-admin coverage remediate --complexity simple

# Include moderate complexity
core-admin coverage remediate --complexity moderate
```

### Code
```python
service = EnhancedSingleFileRemediationService(
    cognitive, auditor, file_path,
    max_complexity="SIMPLE"  # ← Set threshold
)
```

## Example Output

```
Starting enhanced test generation for complex_file.py
Complexity check: Only 3 COMPLEX targets found
Skipping complex_file.py: Too complex for current threshold
Status: skipped
```

```
Starting enhanced test generation for simple_file.py
Complexity check passed: Has 5 SIMPLE, 2 MODERATE targets
Generating tests...
Status: success (14/20 tests passing)
```

## Nightly Mode Strategy

```python
# Process 100 files, skip hard ones
for file in low_coverage_files:
    result = generate_tests(file, max_complexity="SIMPLE")

    if result.status == "skipped":
        print(f"⏭️  {file}: Too hard")
    elif result.status == "success":
        print(f"✅ {file}: +{coverage_delta}%")
```

## Recommendations

- **Nightly batch**: Use `SIMPLE` - fast, high success rate
- **Manual testing**: Use `MODERATE` - balanced
- **Comprehensive**: Use `COMPLEX` - try everything

## Configuration

Default is `MODERATE`. Change in:
- `single_file_remediation_v2.py` line 48
- Or pass as parameter

## Files Added

1. `complexity_filter.py` - New filtering logic
2. `test_generator_v2.py` - Updated with complexity check
3. `single_file_remediation_v2.py` - Updated with parameter
4. `coverage_remediation_service_v2.py` - Updated with parameter
