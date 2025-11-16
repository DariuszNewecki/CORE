#!/usr/bin/env python3
"""
Comprehensive fix for all import issues in CORE.
"""
import os
import re
from pathlib import Path

def fix_file(filepath, fixes):
    """Apply a list of regex fixes to a file."""
    if not os.path.exists(filepath):
        print(f"  File not found: {filepath}")
        return False

    with open(filepath, 'r') as f:
        content = f.read()

    original = content
    for pattern, replacement in fixes:
        content = re.sub(pattern, replacement, content)

    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    return False

def main():
    root = Path('/opt/dev/CORE')
    os.chdir(root)

    print("Applying comprehensive import fixes...")

    # Fix 1: test_guard_drift_cli.py - fix mock paths
    print("\n1. Fixing test_guard_drift_cli.py...")
    if fix_file('tests/admin/test_guard_drift_cli.py', [
        (r'"body\.services\.knowledge_service\.KnowledgeService', r'"services.knowledge_service.KnowledgeService'),
    ]):
        print("   ✓ Fixed mock paths")

    # Fix 2: All files with body.services.knowledge_service imports
    print("\n2. Fixing KnowledgeService imports globally...")
    files_to_fix = [
        'scripts/nightly_coverage_remediation.py',
        'src/api/llm.py',
        'src/api/vectors.py',
        'src/cli/commands/vectorize.py',
        'src/cli/logic/diagnostics.py',
        'src/cli/logic/knowledge_operations.py',
        'src/features/introspection/audit_unassigned_capabilities.py',
        'src/features/introspection/drift_service.py',
        'src/features/metadata/metadata_service.py',
        'src/features/workflow/capabilities_automation_service.py',
    ]

    for filepath in files_to_fix:
        if fix_file(filepath, [
            (r'from body\.services\.knowledge_service import', r'from services.knowledge_service import'),
        ]):
            print(f"   ✓ Fixed {filepath}")

    # Fix 3: test files with 'from core' imports
    print("\n3. Fixing 'core' module imports in test files...")

    # Test files that import from core
    test_files_core = [
        'tests/core/actions/test_healing_actions_extended.py',
        'tests/core/agents/test_self_correction_engine.py',
        'tests/unit/agents/test_intent_translator.py',
        'tests/unit/test_service_registry.py',
    ]

    for filepath in test_files_core:
        if fix_file(filepath, [
            # Map core imports to their new locations
            (r'from core\.actions\.([a-z_]+) import', r'from will.orchestration.\1 import'),
            (r'from core\.agents import', r'from will.agents import'),
            (r'from core\.agents\.([a-z_]+) import', r'from will.agents.\1 import'),
            (r'from core import', r'from will.orchestration import'),
            (r'from core\.', r'from will.orchestration.'),
            (r'import core\.actions', r'import will.orchestration'),
            (r'import core\.agents', r'import will.agents'),
            (r'import core\.', r'import will.orchestration.'),
            (r'import core$', r'import will.orchestration'),
        ]):
            print(f"   ✓ Fixed {filepath}")

    # Fix 4: test_key_management_service.py - features.governance
    print("\n4. Fixing features.governance imports...")
    if fix_file('tests/features/governance/test_key_management_service.py', [
        (r'import features\.governance', r'import mind.governance'),
        (r'from features\.governance', r'from mind.governance'),
        (r'features\.governance\.', r'mind.governance.'),
    ]):
        print("   ✓ Fixed test_key_management_service.py")

    # Fix 5: Apply the fixed files
    print("\n5. Applying pre-generated fixes...")

    fixes_to_copy = [
        ('/mnt/user-data/outputs/policy_loader.py', 'src/mind/governance/policy_loader.py'),
        ('/mnt/user-data/outputs/drift_service.py', 'src/features/introspection/drift_service.py'),
        ('/mnt/user-data/outputs/audit_unassigned_capabilities.py', 'src/features/introspection/audit_unassigned_capabilities.py'),
    ]

    for src, dst in fixes_to_copy:
        if os.path.exists(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(src, 'r') as f:
                content = f.read()
            with open(dst, 'w') as f:
                f.write(content)
            print(f"   ✓ Copied {src} to {dst}")

    print("\n✅ All import fixes applied!")
    print("\nRun 'pytest' to verify the fixes.")

if __name__ == '__main__':
    main()
