# src/system/governance/checks/file_checks.py
"""Auditor checks related to file existence, format, and structure."""

from pathlib import Path
from system.governance.models import AuditFinding, AuditSeverity
from core.validation_pipeline import validate_code

class FileChecks:
    """Container for file-based constitutional checks."""

    def __init__(self, context):
        """Initializes the check with a shared auditor context."""
        self.context = context

    # CAPABILITY: audit.check.required_files
    def check_required_files(self) -> list[AuditFinding]:
        """Verifies that all files declared in meta.yaml exist on disk."""
        findings = []
        check_name = "Required Intent File Existence"
        
        # The list of required files is now dynamically derived from the constitution itself.
        required_files = self._get_known_files_from_meta()
        
        if not required_files:
            findings.append(AuditFinding(AuditSeverity.WARNING, "meta.yaml is empty or missing; cannot check for required files.", check_name))
            return findings

        missing_count = 0
        for file_rel_path in sorted(list(required_files)):
            full_path = self.context.repo_root / file_rel_path
            if not full_path.exists():
                missing_count += 1
                findings.append(AuditFinding(AuditSeverity.ERROR, f"Missing constitutionally-required file: '{file_rel_path}'", check_name))

        if missing_count == 0:
            findings.append(AuditFinding(AuditSeverity.SUCCESS, f"All {len(required_files)} constitutionally-required files are present.", check_name))
            
        return findings

    # CAPABILITY: audit.check.syntax
    def check_syntax(self) -> list[AuditFinding]:
        """Validates the syntax of all .intent YAML/JSON files."""
        findings = []
        check_name = "YAML/JSON Syntax Validity"
        error_findings = []
        files_to_check = list(self.context.intent_dir.rglob("*.yaml")) + list(self.context.intent_dir.rglob("*.json"))
        for file_path in files_to_check:
            if file_path.is_file() and "proposals" not in file_path.parts:
                result = validate_code(str(file_path), file_path.read_text(encoding='utf-8'), quiet=True)
                if result["status"] == "dirty":
                    for violation in result["violations"]:
                        error_findings.append(AuditFinding(AuditSeverity.ERROR, f"Syntax Error: {violation['message']}", check_name, str(file_path.relative_to(self.context.repo_root))))
        
        if not error_findings:
            findings.append(AuditFinding(AuditSeverity.SUCCESS, f"Validated syntax for {len(files_to_check)} YAML/JSON files.", check_name))
        findings.extend(error_findings)
        return findings

    # CAPABILITY: audit.check.orphaned_intent_files
    def check_for_orphaned_intent_files(self) -> list[AuditFinding]:
        """Finds .intent files that are not referenced in meta.yaml."""
        findings = []
        check_name = "Orphaned Intent Files"
        known_files = self._get_known_files_from_meta()
        if not known_files: return []

        ignore_patterns = [".bak", "proposals", ".example"]
        physical_files = {str(p.relative_to(self.context.repo_root)).replace("\\", "/") for p in self.context.intent_dir.rglob("*") if p.is_file() and not any(pat in str(p) for pat in ignore_patterns)}
        
        orphaned_files = sorted(list(physical_files - known_files))
        
        if orphaned_files:
            for orphan in orphaned_files:
                findings.append(AuditFinding(AuditSeverity.WARNING, f"Orphaned intent file: '{orphan}' is not a recognized system file.", check_name))
        else:
            findings.append(AuditFinding(AuditSeverity.SUCCESS, "No orphaned or unrecognized intent files found.", check_name))
        return findings

    def _get_known_files_from_meta(self) -> set:
        """Builds a set of all known intent files by reading .intent/meta.yaml."""
        meta_file_path = self.context.intent_dir / "meta.yaml"
        if not meta_file_path.exists(): return set()

        meta_config = self.context.load_config(meta_file_path, "yaml")
        known_files = set()

        def _recursive_find_paths(data):
            """Recursively finds all file paths declared in the meta configuration."""
            if isinstance(data, dict):
                for value in data.values(): _recursive_find_paths(value)
            elif isinstance(data, list):
                for item in data: _recursive_find_paths(item)
            elif isinstance(data, str) and ('.' in data and '/' in data):
                full_path_str = str(Path(".intent") / data)
                known_files.add(full_path_str.replace("\\", "/"))

        _recursive_find_paths(meta_config)
        
        known_files.add(".intent/meta.yaml")
        known_files.add(".intent/project_manifest.yaml")
        known_files.add(".intent/knowledge/knowledge_graph.json")
        
        schema_dir = self.context.intent_dir / "schemas"
        if schema_dir.exists():
            for schema_file in schema_dir.glob("*.json"):
                known_files.add(str(schema_file.relative_to(self.context.repo_root)).replace("\\", "/"))
        
        return known_files