# src/system/governance/constitutional_auditor.py
"""
CORE Constitutional Auditor
===========================
The single source of truth for validating the entire CORE system's integrity.
"""
import sys
import re
from pathlib import Path
from collections import defaultdict
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from shared.path_utils import get_repo_root
from shared.config_loader import load_config
from shared.schemas.manifest_validator import validate_manifest_entry
from core.validation_pipeline import validate_code
from core.intent_model import IntentModel
from shared.utils.import_scanner import scan_imports_for_file

# CAPABILITY: introspection
# CAPABILITY: alignment_checking
class ConstitutionalAuditor:
    """
    Validates the complete structure and consistency of the .intent/ directory
    and its relationship with the source code.
    """
    def __init__(self):
        """Initializes the auditor, loading all necessary configuration and knowledge files."""
        self.repo_root = get_repo_root()
        self.intent_dir = self.repo_root / ".intent"
        self.src_dir = self.repo_root / "src"
        self.intent_model = IntentModel(self.repo_root)
        self.console = Console()
        self.errors = []
        self.warnings = []
        self.project_manifest = load_config(self.intent_dir / "project_manifest.yaml", "yaml")
        self.knowledge_graph = load_config(self.intent_dir / "knowledge/knowledge_graph.json", "json")
        self.symbols_map = self.knowledge_graph.get("symbols", {})
        self.symbols_list = list(self.symbols_map.values())

    # CAPABILITY: validate_intent_structure
    def run_full_audit(self) -> bool:
        """Run all validation phases and return overall status."""
        self.console.print(Panel("🧠 CORE Constitutional Integrity Audit", style="bold blue"))
        checks = [
            ("Required Intent File Existence", self._check_required_files),
            ("YAML/JSON Syntax Validity", self._validate_syntax),
            ("Project Manifest Integrity", self._validate_project_manifest),
            ("Capability Coverage & Uniqueness", self._check_capability_coverage),
            ("Knowledge Graph Schema Compliance", self._validate_knowledge_graph_schema),
            ("Domain Integrity (Location & Imports)", self._check_domain_integrity),
            ("Docstring & Intent Presence", self._check_docstrings_and_intents),
            ("Dead Code (Unreferenced Symbols)", self._check_for_dead_code),
            ("Orphaned Intent Files", self._check_for_orphaned_intent_files),
        ]
        all_passed = True
        for name, check_fn in checks:
            self.console.rule(f"[bold]🔍 {name}[/bold]")
            if not check_fn():
                all_passed = False
        self._report_final_status(all_passed)
        return all_passed

    def _add_error(self, message: str):
        """Adds an error to the list and prints it."""
        self.errors.append(message)
        self.console.print(f"  [bold red]❌ ERROR:[/] {message}")

    def _add_warning(self, message: str):
        """Adds a warning to the list and prints it."""
        self.warnings.append(message)
        self.console.print(f"  [bold yellow]⚠️ WARNING:[/] {message}")
    
    def _add_success(self, message: str):
        """Prints a success message."""
        self.console.print(f"  [bold green]✅ PASS:[/] {message}")

    def _check_required_files(self) -> bool:
        """Ensure all critical intent files exist."""
        required = [
            "project_manifest.yaml", "mission/principles.yaml", "mission/northstar.yaml",
            "policies/intent_guard.yaml", "policies/safety_policies.yaml",
            "knowledge/knowledge_graph.json", "knowledge/source_structure.yaml",
        ]
        missing = [p for p in required if not (self.intent_dir / p).exists()]
        for path in missing:
            self._add_error(f"Missing critical file: .intent/{path}")
        if not missing:
            self._add_success("All critical intent files are present.")
        return not missing

    def _validate_syntax(self) -> bool:
        """Validate YAML/JSON syntax across all intent files."""
        initial_error_count = len(self.errors)
        files_to_check = list(self.intent_dir.rglob("*.yaml")) + list(self.intent_dir.rglob("*.json"))
        for file_path in files_to_check:
            if file_path.is_file():
                result = validate_code(str(file_path), file_path.read_text(encoding='utf-8'))
                if result["status"] == "dirty":
                    for err in result["errors"]:
                        self._add_error(f"Syntax Error in {file_path.relative_to(self.repo_root)}: {err}")
        passed = len(self.errors) == initial_error_count
        if passed:
            self._add_success(f"Validated syntax for {len(files_to_check)} YAML/JSON files.")
        return passed

    def _validate_project_manifest(self) -> bool:
        """Ensure project_manifest.yaml is structurally sound."""
        initial_error_count = len(self.errors)
        required_keys = ["name", "intent", "required_capabilities", "active_agents"]
        for key in required_keys:
            if key not in self.project_manifest:
                self._add_error(f"project_manifest.yaml missing required key: '{key}'")
        passed = len(self.errors) == initial_error_count
        if passed:
            self._add_success("project_manifest.yaml contains all required keys.")
        return passed

    def _check_capability_coverage(self) -> bool:
        """Check for missing or duplicate capability implementations."""
        initial_error_count = len(self.errors)
        required_caps = set(self.project_manifest.get("required_capabilities", []))
        implemented_caps = {f.get("capability") for f in self.symbols_list if f.get("capability") != "unassigned"}
        missing = sorted(list(required_caps - implemented_caps))
        if missing:
            self._add_error(f"Missing capability implementations for: {missing}")
        unrecognized = sorted(list(implemented_caps - required_caps))
        if unrecognized:
            self._add_warning(f"Unrecognized capabilities in code not in project_manifest.yaml: {unrecognized}")
        passed = len(self.errors) == initial_error_count
        if passed and not unrecognized:
            self._add_success("All required capabilities are implemented and recognized.")
        elif passed:
            self._add_success("All required capabilities are implemented.")
        return passed

    def _validate_knowledge_graph_schema(self) -> bool:
        """Validate each entry in the knowledge graph against its JSON schema."""
        initial_error_count = len(self.errors)
        for key, entry in self.symbols_map.items():
            is_valid, validation_errors = validate_manifest_entry(entry, "knowledge_graph_entry.schema.json")
            if not is_valid:
                for err in validation_errors:
                    self._add_error(f"Knowledge Graph entry '{key}' schema error: {err}")
        passed = len(self.errors) == initial_error_count
        if passed:
            self._add_success(f"All {len(self.symbols_map)} symbols in knowledge graph pass schema validation.")
        return passed
        
    def _check_domain_integrity(self) -> bool:
        """Validate domain declarations and cross-domain imports."""
        initial_error_count = len(self.errors)
        for entry in self.symbols_list:
            file_path = self.repo_root / entry.get("file", "")
            if not file_path.exists():
                self._add_warning(f"File '{entry.get('file')}' from knowledge graph not found on disk.")
                continue
            declared_domain = entry.get("domain")
            actual_domain = self.intent_model.resolve_domain_for_path(file_path.relative_to(self.repo_root))
            if declared_domain != actual_domain:
                self._add_error(f"Domain Mismatch for '{entry.get('key')}': Declared='{declared_domain}', Actual='{actual_domain}'")
            allowed = set(self.intent_model.get_domain_permissions(actual_domain)) | {actual_domain}
            imports = scan_imports_for_file(file_path)
            for imp in imports:
                if imp.startswith("src."): imp = imp[4:]
                if imp.startswith(("core.", "shared.", "system.", "agents.")):
                    imp_path_parts = imp.split('.')
                    potential_path = self.src_dir.joinpath(*imp_path_parts)
                    check_path = potential_path.with_suffix(".py")
                    if not check_path.exists(): check_path = potential_path 
                    imp_domain = self.intent_model.resolve_domain_for_path(check_path)
                    if imp_domain and imp_domain not in allowed:
                         self._add_error(f"Forbidden Import in '{entry.get('file')}': Domain '{actual_domain}' cannot import '{imp}' from forbidden domain '{imp_domain}'")
        passed = len(self.errors) == initial_error_count
        if passed:
             self._add_success("Domain locations and import boundaries are valid.")
        return passed

    def _check_docstrings_and_intents(self) -> bool:
        """Check for missing docstrings or weak, generic intents."""
        initial_warning_count = len(self.warnings)
        for entry in self.symbols_list:
            if entry.get("type") != "ClassDef" and not entry.get("docstring"):
                self._add_warning(f"Missing Docstring in '{entry.get('file')}': Symbol '{entry.get('name')}'")
            if "Provides functionality for the" in entry.get("intent", ""):
                 self._add_warning(f"Generic Intent in '{entry.get('file')}': Symbol '{entry.get('name')}' has a weak intent statement.")
        if len(self.warnings) == initial_warning_count:
            self._add_success("All symbols have docstrings and specific intents.")
        return True

    # CAPABILITY: self_review
    def _check_for_dead_code(self) -> bool:
        """Finds symbols that are not entry points and are never called."""
        all_called_symbols = set()
        for symbol in self.symbols_list:
            all_called_symbols.update(symbol.get("calls", []))

        initial_warning_count = len(self.warnings)
        for symbol in self.symbols_list:
            name = symbol["name"]
            
            # A symbol is NOT dead if ANY of these are true:
            # 1. It is marked as private or a test.
            if name.startswith(('_', 'test_')):
                continue
            # 2. It is called by another symbol in our codebase.
            if name in all_called_symbols:
                continue
            # 3. The Knowledge Graph has identified it as any kind of entry point.
            if symbol.get("entry_point_type"):
                continue

            # If none of the above are true, it is unreferenced.
            self._add_warning(f"Potentially dead code: Symbol '{name}' in '{symbol['file']}' appears to be unreferenced.")
            
        if len(self.warnings) == initial_warning_count:
            self._add_success("No unreferenced public symbols found.")
        return True

    def _check_for_orphaned_intent_files(self) -> bool:
        """Finds .intent files that are not part of the core system configuration."""
        known_files = {
            ".intent/project_manifest.yaml", ".intent/mission/principles.yaml",
            ".intent/mission/northstar.yaml", ".intent/mission/manifesto.md",
            ".intent/policies/intent_guard.yaml", ".intent/policies/safety_policies.yaml",
            ".intent/policies/security_intents.yaml", ".intent/knowledge/source_structure.yaml",
            ".intent/knowledge/knowledge_graph.json", ".intent/knowledge/agent_roles.yaml",
            ".intent/knowledge/capability_tags.yaml", ".intent/knowledge/file_handlers.yaml",
            ".intent/knowledge/entry_point_patterns.yaml",
            ".intent/evaluation/audit_checklist.yaml", ".intent/evaluation/score_policy.yaml",
            ".intent/config/local_mode.yaml", ".intent/meta.yaml",
            ".intent/schemas/knowledge_graph_entry.schema.json", # <-- ADDED THIS LINE
        }
        ignore_patterns = [".log", ".tmp", ".bak", "change_log.json"] # Ignoring change_log
        physical_files = {str(p.relative_to(self.repo_root)).replace("\\", "/") for p in self.intent_dir.rglob("*") if p.is_file() and not any(pat in p.name for pat in ignore_patterns)}
        orphaned_files = sorted(list(physical_files - known_files))
        initial_warning_count = len(self.warnings)
        for orphan in orphaned_files:
            self._add_warning(f"Orphaned intent file: '{orphan}' is not a recognized system file.")
        if len(self.warnings) == initial_warning_count:
            self._add_success("No orphaned or unrecognized intent files found.")
        return True

    def _report_final_status(self, passed: bool):
        """Print final summary report."""
        self.console.print()
        if passed:
            self.console.print(Panel(f"✅ ALL CHECKS PASSED ({len(self.warnings)} warnings)", style="bold green", expand=False))
        else:
            self.console.print(Panel(f"❌ AUDIT FAILED: {len(self.errors)} error(s) and {len(self.warnings)} warning(s) found.", style="bold red"))
            if self.errors:
                error_table = Table("🚨 Critical Errors", style="red")
                for err in self.errors: error_table.add_row(err)
                self.console.print(error_table)
        if self.warnings:
            warning_table = Table("⚠️ Warnings", style="yellow")
            for warn in self.warnings: warning_table.add_row(warn)
            self.console.print(warning_table)

def main():
    """CLI entry point for the Constitutional Auditor."""
    auditor = ConstitutionalAuditor()
    try:
        success = auditor.run_full_audit()
        sys.exit(0 if success else 1)
    except FileNotFoundError as e:
        print(f"\n[bold red]FATAL ERROR: A required file was not found.[/bold red]\nDetails: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[bold red]An unexpected error occurred during the audit: {e}[/bold red]")
        sys.exit(1)

if __name__ == "__main__":
    main()