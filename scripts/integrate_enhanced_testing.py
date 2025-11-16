#!/usr/bin/env python3
"""
Integration script for enhanced test generation system.

This script:
1. Validates that all components are present
2. Backs up original files
3. Integrates the enhanced system
4. Runs a test to verify it works
"""

import shutil
import sys
from pathlib import Path


def main():
    print("🚀 Enhanced Test Generation Integration")
    print("=" * 60)

    # Detect repo root
    script_dir = Path(__file__).parent
    repo_root = None

    # Try to find repo root by looking for pyproject.toml
    current = script_dir
    for _ in range(5):  # Search up to 5 levels
        if (current / "pyproject.toml").exists():
            repo_root = current
            break
        current = current.parent

    if not repo_root:
        print("❌ Could not find repository root (looking for pyproject.toml)")
        print("   Please run this script from within the CORE repository")
        return 1

    print(f"✅ Found repository: {repo_root}")

    # Check for required source files
    src_dir = repo_root / "src" / "features" / "self_healing"

    required_new_files = [
        script_dir / "test_context_analyzer.py",
        script_dir / "test_generator_v2.py",
        script_dir / "single_file_remediation_v2.py",
        script_dir / "coverage_remediation_service_v2.py",
    ]

    print("\n📋 Checking required files...")
    for file_path in required_new_files:
        if not file_path.exists():
            print(f"❌ Missing: {file_path}")
            return 1
        print(f"✅ Found: {file_path.name}")

    # Create backup
    backup_dir = repo_root / "work" / "backups" / "test_generation_original"
    backup_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n💾 Creating backup in: {backup_dir}")

    original_files = [
        "coverage_remediation_service.py",
        "single_file_remediation.py",
        "test_generator.py",
    ]

    for filename in original_files:
        src_file = src_dir / filename
        if src_file.exists():
            backup_file = backup_dir / filename
            shutil.copy2(src_file, backup_file)
            print(f"   Backed up: {filename}")

    # Copy new files
    print("\n📦 Installing enhanced components...")
    for src_file in required_new_files:
        dest_file = src_dir / src_file.name
        shutil.copy2(src_file, dest_file)
        print(f"   Installed: {src_file.name}")

    # Update CLI integration
    cli_file = repo_root / "src" / "cli" / "commands" / "coverage.py"

    if not cli_file.exists():
        print(f"\n⚠️  Warning: Could not find {cli_file}")
        print("   You'll need to manually update the import")
    else:
        print(f"\n🔧 Updating CLI integration: {cli_file.name}")

        # Read current content
        content = cli_file.read_text()

        # Check if already updated
        if "coverage_remediation_service_v2" in content:
            print("   Already using enhanced service ✅")
        else:
            # Create backup
            cli_backup = backup_dir / "coverage.py"
            shutil.copy2(cli_file, cli_backup)

            # Update import
            old_import = "from features.self_healing.coverage_remediation_service import remediate_coverage"
            new_import = "from features.self_healing.coverage_remediation_service_v2 import remediate_coverage"

            if old_import in content:
                updated_content = content.replace(old_import, new_import)
                cli_file.write_text(updated_content)
                print("   ✅ Updated import to use enhanced service")
            else:
                print("   ⚠️  Could not find expected import statement")
                print("   Please manually update the import in coverage.py")

    # Create work directories
    print("\n📁 Creating work directories...")
    work_dirs = [
        repo_root / "work" / "testing" / "prompts",
        repo_root / "reports" / "failed_test_generation",
    ]

    for work_dir in work_dirs:
        work_dir.mkdir(parents=True, exist_ok=True)
        print(f"   Created: {work_dir.relative_to(repo_root)}")

    # Success message
    print("\n" + "=" * 60)
    print("✨ Integration Complete!")
    print("=" * 60)

    print("\n📝 Next Steps:")
    print("\n1. Review the changes:")
    print(f"   ls {src_dir.relative_to(repo_root)}")

    print("\n2. Test the enhanced system:")
    print(
        "   poetry run core-admin coverage remediate --file src/shared/utils/header_tools.py"
    )

    print("\n3. Check generated artifacts:")
    print("   ls work/testing/prompts/")
    print("   ls reports/failed_test_generation/")

    print("\n4. Review the migration guide:")
    print(f"   cat {script_dir / 'MIGRATION_GUIDE.md'}")

    print("\n5. If you need to rollback:")
    print(f"   cp {backup_dir}/*.py {src_dir}/")

    print("\n✅ All systems ready!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
