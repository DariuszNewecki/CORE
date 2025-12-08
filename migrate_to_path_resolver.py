#!/usr/bin/env python3
"""
Migration script: Replace hardcoded REPO_ROOT path construction with settings.paths

This script automatically migrates all instances of hardcoded path construction
to use the new PathResolver interface.

Usage:
    python migrate_to_path_resolver.py --dry-run  # Preview changes
    python migrate_to_path_resolver.py --apply    # Apply changes
"""

from pathlib import Path


REPO_ROOT = Path(__file__).parent

MIGRATIONS = [
    # File: src/services/repositories/db/common.py
    {
        "file": "src/services/repositories/db/common.py",
        "changes": [
            {
                "line": 32,
                "old": 'META_YAML_PATH = REPO_ROOT / ".intent" / "meta.yaml"',
                "new": 'META_YAML_PATH = settings.paths.intent_root / "meta.yaml"',
                "add_import": "from shared.config import settings",
            },
            {
                "line": 44,
                "old": 'db_policy_path = REPO_ROOT / ".intent" / db_policy_path_str',
                "new": "db_policy_path = settings.paths.intent_root / db_policy_path_str",
            },
        ],
    },
    # File: src/features/self_healing/enrichment_service.py
    {
        "file": "src/features/self_healing/enrichment_service.py",
        "changes": [
            {
                "line": 51,
                "old": 'REPO_ROOT / ".intent/mind/prompts/enrich_symbol.prompt"',
                "new": 'settings.paths.prompt("enrich_symbol")',
                "add_import": "from shared.config import settings",
            },
        ],
    },
    # File: src/features/self_healing/prune_private_capabilities.py
    {
        "file": "src/features/self_healing/prune_private_capabilities.py",
        "changes": [
            {
                "line": 62,
                "old": "file_path = REPO_ROOT / file_path_str",
                "new": "file_path = settings.paths.repo_root / file_path_str",
                "add_import": "from shared.config import settings",
            },
        ],
    },
    # File: src/features/self_healing/header_service.py
    {
        "file": "src/features/self_healing/header_service.py",
        "changes": [
            {
                "line": 133,
                "old": "file_path = REPO_ROOT / file_path_str",
                "new": "file_path = settings.paths.repo_root / file_path_str",
                "add_import": "from shared.config import settings",
            },
            {
                "line": 168,
                "old": '(REPO_ROOT / file_path_str).write_text(new_code, "utf-8")',
                "new": '(settings.paths.repo_root / file_path_str).write_text(new_code, "utf-8")',
            },
        ],
    },
    # File: src/features/self_healing/complexity_service.py
    {
        "file": "src/features/self_healing/complexity_service.py",
        "changes": [
            {
                "line": 42,
                "old": 'proposal_dir = REPO_ROOT / ".intent" / "proposals"',
                "new": "proposal_dir = settings.paths.proposals_dir",
                "add_import": "from shared.config import settings",
            },
            {
                "line": 111,
                "old": 'source_code = (REPO_ROOT / file_rel_path).read_text(encoding="utf-8")',
                "new": 'source_code = (settings.paths.repo_root / file_rel_path).read_text(encoding="utf-8")',
            },
            {
                "line": 148,
                "old": "(REPO_ROOT / file_rel_path).unlink()",
                "new": "(settings.paths.repo_root / file_rel_path).unlink()",
            },
            {
                "line": 150,
                "old": '(REPO_ROOT / path).write_text(code, encoding="utf-8")',
                "new": '(settings.paths.repo_root / path).write_text(code, encoding="utf-8")',
            },
        ],
    },
    # File: src/features/self_healing/fix_manifest_hygiene.py
    {
        "file": "src/features/self_healing/fix_manifest_hygiene.py",
        "changes": [
            {
                "line": 22,
                "old": 'DOMAINS_DIR = REPO_ROOT / ".intent" / "mind" / "knowledge" / "domains"',
                "new": 'DOMAINS_DIR = settings.paths.mind_root / "knowledge" / "domains"',
                "add_import": "from shared.config import settings",
            },
        ],
    },
    # File: src/features/self_healing/linelength_service.py
    {
        "file": "src/features/self_healing/linelength_service.py",
        "changes": [
            {
                "line": 118,
                "old": 'src_dir = REPO_ROOT / "src"',
                "new": 'src_dir = settings.paths.repo_root / "src"',
                "add_import": "from shared.config import settings",
            },
        ],
    },
    # File: src/features/self_healing/docstring_service.py
    {
        "file": "src/features/self_healing/docstring_service.py",
        "changes": [
            {
                "line": 55,
                "old": 'file_path = REPO_ROOT / symbol["file_path"]',
                "new": 'file_path = settings.paths.repo_root / symbol["file_path"]',
                "add_import": "from shared.config import settings",
            },
        ],
    },
]


def apply_migrations(dry_run=True):
    """Apply all migrations."""
    for migration in MIGRATIONS:
        file_path = REPO_ROOT / migration["file"]

        if not file_path.exists():
            print(f"⚠️  File not found: {file_path}")
            continue

        print(f"\n📝 Processing: {migration['file']}")

        # Read file
        content = file_path.read_text()
        lines = content.split("\n")

        # Check if we need to add import
        needs_import = any(change.get("add_import") for change in migration["changes"])

        if needs_import and "from shared.config import settings" not in content:
            # Find where to insert import (after other imports)
            insert_line = 0
            for i, line in enumerate(lines):
                if line.startswith("from ") or line.startswith("import "):
                    insert_line = i + 1

            lines.insert(insert_line, "from shared.config import settings")
            print("  ✅ Added import: from shared.config import settings")

        # Apply changes
        for change in migration["changes"]:
            old = change["old"]
            new = change["new"]

            # Find and replace
            modified = False
            for i, line in enumerate(lines):
                if old in line:
                    lines[i] = line.replace(old, new)
                    modified = True
                    print(f"  ✅ Line {i+1}: {old[:50]}... → {new[:50]}...")

            if not modified:
                print(f"  ⚠️  Could not find: {old[:50]}...")

        # Write back
        if not dry_run:
            file_path.write_text("\n".join(lines))
            print("  💾 Saved changes")
        else:
            print("  🔍 DRY RUN - no changes written")


if __name__ == "__main__":
    import sys

    dry_run = "--apply" not in sys.argv

    if dry_run:
        print("=" * 70)
        print("DRY RUN MODE - No changes will be written")
        print("Use --apply to actually modify files")
        print("=" * 70)
    else:
        print("=" * 70)
        print("APPLYING CHANGES")
        print("=" * 70)

    apply_migrations(dry_run=dry_run)

    print("\n" + "=" * 70)
    if dry_run:
        print("✅ Preview complete. Run with --apply to make changes.")
    else:
        print("✅ Migration complete!")
        print("\nNext steps:")
        print("  1. Run tests: pytest tests/")
        print("  2. Check git diff: git diff")
        print(
            "  3. Commit changes: git add -A && git commit -m 'Migrate to PathResolver'"
        )
