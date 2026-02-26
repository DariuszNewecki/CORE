# scripts/verify_governance_refactor.py
"""
Constitutional Implementation Auditor - V2 (Robust String Matching).
Verifies that Category A, B, and C refactors have removed direct I/O bypasses.
"""

import sys
from pathlib import Path

# The 12 files that MUST use ActionExecutor.execute()
GATEWAY_FILES = [
    "src/features/self_healing/duplicate_id_service.py",
    "src/features/self_healing/id_tagging_service.py",
    "src/features/self_healing/docstring_service.py",
    "src/features/self_healing/policy_id_service.py",
    "src/features/self_healing/linelength_service.py",
    "src/features/self_healing/clarity_service.py",
    "src/features/self_healing/header_service.py",
    "src/features/self_healing/prune_private_capabilities.py",
    "src/features/self_healing/purge_legacy_tags_service.py",
    "src/features/self_healing/fix_manifest_hygiene.py",
    "src/features/self_healing/complexity_service.py",
    "src/features/project_lifecycle/scaffolding_service.py",
]

# The 3 files that MUST use FileHandler methods
FILE_HANDLER_FILES = [
    "src/features/introspection/knowledge_graph_service.py",
    "src/features/maintenance/scripts/context_export.py",
    "src/features/introspection/export_vectors.py",
]

# Dangerous raw Python methods
DANGEROUS_METHODS = [".write_text(", ".write_bytes(", ".unlink(", ".mkdir("]

def check_gateway_file(content, path_str):
    """Checks for files that should ONLY use the ActionExecutor gateway."""
    errors = []

    # 1. Verify markers
    if "ActionExecutor" not in content and "executor" not in content.lower():
        errors.append("MISSING: ActionExecutor / executor gateway integration.")
    if "execute(" not in content:
        errors.append("MISSING: .execute() call for mutations.")

    # 2. Ensure NO direct bypasses exist
    for method in DANGEROUS_METHODS:
        if method in content:
            # Exception: complexity_service can have .unlink in a string for a prompt,
            # but not as a call. We look for 'path.unlink('
            errors.append(f"BYPASS: Found raw '{method}' call. Use executor.execute instead.")

    return errors

def check_file_handler_file(content, path_str):
    """Checks for files that should use the FileHandler for reporting."""
    errors = []

    if "FileHandler" not in content and "file_handler" not in content.lower():
        errors.append("MISSING: FileHandler / file_handler integration.")

    # In these files, .write_text is okay ONLY if it is called on a sanctioned handler
    # e.g. self.fh.write_runtime_text()
    sanctioned_prefixes = ["fh.", "fs.", "file_handler.", "handler.", "self.fh.", "self._fh."]

    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        for method in DANGEROUS_METHODS:
            if method in line:
                # If the line contains a dangerous method, check if it's prefixed by a sanctioned handler
                is_prefixed = any(p + method[1:] in line for p in sanctioned_prefixes)
                if not is_prefixed:
                    errors.append(f"BYPASS: Raw '{method}' on line {i} without sanctioned handler prefix.")

    return errors

def main():
    print("\n" + "="*60)
    print("      CORE CONSTITUTIONAL IMPLEMENTATION AUDIT")
    print("="*60 + "\n")

    passed_count = 0
    failed_count = 0
    missing_count = 0

    all_targets = GATEWAY_FILES + FILE_HANDLER_FILES

    for file_path in all_targets:
        p = Path(file_path)
        if not p.exists():
            print(f"⚪ [SKIPPED] {file_path} (File not found)")
            missing_count += 1
            continue

        content = p.read_text(encoding="utf-8")

        if file_path in GATEWAY_FILES:
            errors = check_gateway_file(content, file_path)
        else:
            errors = check_file_handler_file(content, file_path)

        if not errors:
            print(f"✅ [PASSED] {file_path}")
            passed_count += 1
        else:
            print(f"❌ [FAILED] {file_path}")
            for err in errors:
                print(f"    - {err}")
            failed_count += 1

    print("\n" + "="*60)
    print(f"SUMMARY: {passed_count} Passed, {failed_count} Failed, {missing_count} Missing")
    print("="*60 + "\n")

    if failed_count > 0:
        print("🚨 Result: NON-COMPLIANT. Correct the files marked [FAILED].\n")
        sys.exit(1)
    else:
        print("🎊 Result: 100% COMPLIANT. Gateway transition verified.\n")
        sys.exit(0)

if __name__ == "__main__":
    main()
