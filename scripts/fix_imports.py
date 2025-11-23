#!/usr/bin/env python3
"""
Script to fix all import issues in CORE codebase.
"""

import re
from pathlib import Path


def fix_imports_in_file(filepath):
    """Fix imports in a single file."""
    if not filepath.exists():
        return False

    with open(filepath) as f:
        content = f.read()

    original_content = content

    # Fix body.services.knowledge_service -> services.knowledge_service
    content = re.sub(
        r"from body\.services\.knowledge_service import",
        "from services.knowledge_service import",
        content,
    )

    # Fix incorrect core imports (should be relative or absolute from src/)
    # For test files that import from 'core' module
    if "/tests/" in str(filepath):
        # Tests should use absolute imports from src
        content = re.sub(
            r"from core\.([a-z_]+)\.([a-z_]+) import",
            r"from will.orchestration.\1.\2 import",
            content,
        )
        content = re.sub(
            r"import core\.([a-z_]+)\.([a-z_]+)",
            r"import will.orchestration.\1.\2",
            content,
        )
        # Fix core.agents -> will.agents
        content = re.sub(
            r"from core\.agents import", r"from will.agents import", content
        )
        content = re.sub(r"import core\.agents", r"import will.agents", content)

    # Fix features.governance imports that may be wrong
    content = re.sub(
        r"import features\.governance\.", r"import mind.governance.", content
    )

    if content != original_content:
        with open(filepath, "w") as f:
            f.write(content)
        return True
    return False


def main():
    """Main function to fix imports across the codebase."""
    root = Path("/opt/dev/CORE")

    # Files to fix based on the errors
    files_to_fix = [
        # Files with body.services.knowledge_service imports
        "scripts/nightly_coverage_remediation.py",
        "src/api/llm.py",
        "src/api/vectors.py",
        "src/cli/commands/vectorize.py",
        "src/cli/logic/diagnostics.py",
        "src/cli/logic/knowledge_operations.py",
        "src/features/introspection/audit_unassigned_capabilities.py",
        "src/features/introspection/drift_service.py",
        "src/features/metadata/metadata_service.py",
        "src/features/workflow/capabilities_automation_service.py",
        "tests/admin/test_guard_drift_cli.py",
        # Test files with ModuleNotFoundError: No module named 'core'
        "tests/core/actions/test_healing_actions_extended.py",
        "tests/core/agents/test_self_correction_engine.py",
        "tests/unit/agents/test_intent_translator.py",
        "tests/unit/test_service_registry.py",
        # Test files with features.governance issues
        "tests/features/governance/test_key_management_service.py",
        # Files with mind.governance.policy_loader issues
        "tests/mind/governance/test_policy_loader.py",
    ]

    fixed_count = 0
    for file_path in files_to_fix:
        full_path = root / file_path
        if full_path.exists():
            if fix_imports_in_file(full_path):
                print(f"Fixed imports in: {file_path}")
                fixed_count += 1
        else:
            print(f"File not found: {file_path}")

    # Also scan all Python files for the problematic imports
    print("\nScanning all Python files for import issues...")
    for py_file in root.rglob("*.py"):
        if "venv" in str(py_file) or ".venv" in str(py_file):
            continue
        if fix_imports_in_file(py_file):
            print(f"Fixed imports in: {py_file.relative_to(root)}")
            fixed_count += 1

    print(f"\nTotal files fixed: {fixed_count}")


if __name__ == "__main__":
    main()
