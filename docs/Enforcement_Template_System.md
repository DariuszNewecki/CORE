# Enforcement Template System

## Overview

The Enforcement Template System makes it trivial to add new constitutional checks by declaring WHAT to verify rather than HOW to verify it.

## Architecture

```
BaseCheck (abstract)
    └── RuleEnforcementCheck (template)
            └── SafetyRulesCheck (concrete, declarative)
            └── SecretsManagementCheck (concrete, declarative)
            └── EventsCheck (concrete, declarative)
            └── ... (add more as needed)
```

## Components

### 1. `enforcement_methods.py`
Defines reusable verification strategies:

- **PathProtectionEnforcement** - Verifies protected paths in IntentGuard
- **CodePatternEnforcement** - Detects patterns via AST scanning
- **AuditLoggingEnforcement** - Validates audit metadata exists
- **SingleInstanceEnforcement** - Ensures exactly one instance
- **DatabaseSSOTEnforcement** - Verifies data in DB not files

### 2. `rule_enforcement_check.py`
Template that handles all boilerplate:

- Loads policy files
- Finds rules by ID
- Runs enforcement verifications
- Collects findings

### 3. Concrete Checks (e.g., `safety_rules_check.py`)
Simple declarations:

```python
class SafetyRulesCheck(RuleEnforcementCheck):
    policy_file = Path(".intent/charter/standards/operations/safety.yaml")
    
    enforcement_methods = [
        PathProtectionEnforcement(
            rule_id="safety.charter_immutable",
            expected_patterns=[".intent/charter/**"],
        ),
        SingleInstanceEnforcement(
            rule_id="safety.single_active_constitution",
            target_file="charter/constitution/ACTIVE",
        ),
    ]
```

## Adding a New Check

### Step 1: Create the check file

```python
# src/mind/governance/checks/your_new_check.py

from pathlib import Path
from typing import ClassVar
from mind.governance.checks.rule_enforcement_check import RuleEnforcementCheck
from mind.governance.enforcement_methods import PathProtectionEnforcement

class YourNewCheck(RuleEnforcementCheck):
    policy_file = Path(".intent/charter/standards/your_policy.yaml")
    
    enforcement_methods = [
        PathProtectionEnforcement(
            rule_id="your.rule.id",
            expected_patterns=["some/path/**"],
        ),
    ]
```

### Step 2: Register it (if using entry points)

Add to `pyproject.toml`:
```toml
[project.entry-points."core.governance_checks"]
your_new_check = "mind.governance.checks.your_new_check:YourNewCheck"
```

### Step 3: Run audit

```bash
core-admin audit
```

That's it! The template handles everything else.

## Benefits

1. **Consistency** - All checks follow same pattern
2. **Reusability** - Enforcement methods used across checks
3. **Maintainability** - Easy to update verification logic
4. **Discoverability** - Clear what's being enforced
5. **Velocity** - Add new rules in minutes, not hours

## Current Coverage

### Implemented:
- ✅ SafetyRulesCheck (6 rules)
- ✅ SecretsManagementCheck (3 rules)

### TODO (17 gaps):
- ❌ EventsCheck (3 rules: cloudevents_compliance, payload_immutability, topic_naming)
- ❌ StyleCheck (4 rules: formatter_required, linter_required, fail_on_style_in_ci, etc.)
- ❌ ToolsCheck (2 rules: explicit_return_contract, type_mapping_strictness)
- ❌ ... (remaining 8 gaps)

## Migration Path

### Old way (custom logic):
```python
class SomeCheck(BaseCheck):
    def execute(self):
        findings = []
        # 50 lines of custom verification logic
        # Load file, parse YAML, check rules, etc.
        return findings
```

### New way (declarative):
```python
class SomeCheck(RuleEnforcementCheck):
    policy_file = Path("...")
    enforcement_methods = [
        PathProtectionEnforcement(...),
    ]
```

## Next Steps

1. Add remaining enforcement method types as needed
2. Migrate existing checks to use template
3. Add all 17 missing rule checks
4. Achieve 100% enforcement coverage