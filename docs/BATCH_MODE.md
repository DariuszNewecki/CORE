# Batch Mode - Process Multiple Files

## New CLI Commands

```bash
# Process 1 file (test mode)
poetry run core-admin coverage remediate --count 1 --complexity simple

# Process 5 simple files (nightly mode)
poetry run core-admin coverage remediate --count 5 --complexity simple

# Process 10 moderate files (balanced)
poetry run core-admin coverage remediate --count 10 --complexity moderate

# Process 20 files, try everything
poetry run core-admin coverage remediate --count 20 --complexity complex
```

## How It Works

1. **Find candidates**: All files < 75% coverage
2. **Filter by complexity**: Only files matching threshold
3. **Sort by coverage**: Lowest first (biggest wins)
4. **Process N files**: Up to your count
5. **Report results**: Summary table

## Output Example

```
🔍 Step 1: Finding candidate files...
Found 150 files below 75% coverage
Filtering by complexity: SIMPLE
✅ 45 files match complexity threshold

📝 Step 2: Processing 5 files...

File 1/5: header_tools.py (40.5% coverage)
  ✅ Partial success: 14/20 tests (70%)

File 2/5: parsing.py (25.3% coverage)
  ✅ All tests passed!

File 3/5: crypto.py (0.0% coverage)
  ⏭️  Skipped: Too complex for SIMPLE threshold

File 4/5: time.py (30.1% coverage)
  ✅ Partial success: 8/10 tests (80%)

File 5/5: config_loader.py (15.7% coverage)
  ❌ Failed: No code block generated

📊 Batch Summary
┌────────────────┬──────────┬───────┬──────────┐
│ File           │ Status   │ Tests │ Coverage │
├────────────────┼──────────┼───────┼──────────┤
│ header_tools   │ ⚠️  Partial │ 14/20 │ 40.5%   │
│ parsing        │ ✅ Success │ All   │ 25.3%   │
│ crypto         │ ⏭️  Skipped │ -     │ 0.0%    │
│ time           │ ⚠️  Partial │ 8/10  │ 30.1%   │
│ config_loader  │ ❌ Failed  │ -     │ 15.7%   │
└────────────────┴──────────┴───────┴──────────┘

Results:
  ✅ Success: 1
  ⚠️  Partial: 2
  ❌ Failed: 1
  ⏭️  Skipped: 1
```

## Success Criteria

- **Success**: All tests pass
- **Partial**: 50%+ tests pass (still useful!)
- **Failed**: < 50% tests pass
- **Skipped**: Too complex for threshold

## Strategy Recommendations

### Nightly Mode (Automated)
```bash
# Run every night at 2 AM
poetry run core-admin coverage remediate --count 10 --complexity simple
```
- Only trivial files
- High success rate
- Gradual improvement

### Manual Testing
```bash
poetry run core-admin coverage remediate --count 5 --complexity moderate
```
- Balanced approach
- Good coverage gains
- Reasonable success rate

### Aggressive
```bash
poetry run core-admin coverage remediate --count 20 --complexity complex
```
- Try everything
- Some will fail
- Maximum coverage attempts

## Files to Install

```bash
cd /opt/dev/CORE

cp batch_remediation_service.py src/features/self_healing/
cp coverage.py src/cli/commands/
cp complexity_filter.py src/features/self_healing/
cp test_generator_v2.py src/features/self_healing/
cp single_file_remediation_v2.py src/features/self_healing/
cp coverage_remediation_service_v2.py src/features/self_healing/
```

## Test It

```bash
# Start small - just 1 file
poetry run core-admin coverage remediate --count 1 --complexity simple
```

Should process the easiest file in your codebase and show results!
