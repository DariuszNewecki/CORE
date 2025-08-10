# src/system/governance/constitutional_auditor.py
"""
CORE Constitutional Auditor Orchestrator
=======================================
Discovers and runs modular checks to validate the system's integrity.
"""
import sys
import io
import inspect
import importlib
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Optional, Callable, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from shared.path_utils import get_repo_root
from shared.config_loader import load_config
from core.intent_model import IntentModel
from shared.logger import getLogger
from system.governance.models import AuditFinding, AuditSeverity

log = getLogger(__name__)

# CAPABILITY: introspection
# CAPABILITY: alignment_checking
class ConstitutionalAuditor:
    """Orchestrates the discovery and execution of all constitutional checks."""
    
    class _LoggingBridge(io.StringIO):
        """A file-like object that redirects writes to the logger."""
        def write(self, s: str):
            """Redirects the write to the logger info stream."""
            cleaned_s = s.strip()
            if cleaned_s:
                log.info(cleaned_s)

    def __init__(self, repo_root_override: Optional[Path] = None):
        """
        Initializes the auditor, loading all necessary configuration and knowledge files.
        
        Args:
            repo_root_override (Optional[Path]): 
                If provided, the auditor will run against this directory as its root.
                This is crucial for the 'canary' validation process.
        """
        self.repo_root = repo_root_override or get_repo_root()

        # --- THIS IS THE FIX ---
        # If we are in a temporary "canary" environment, we must explicitly load
        # the .env file from that environment so the canary can pass its own health checks.
        if repo_root_override:
            dotenv_path = self.repo_root / ".env"
            if dotenv_path.exists():
                load_dotenv(dotenv_path=dotenv_path, override=True)
                log.info(f"   -> Canary auditor loaded environment from {dotenv_path}")
        # --- END OF FIX ---
        
        # Create a shared context for all checks
        self.context = self.AuditorContext(self.repo_root)

        self.console = Console(file=self._LoggingBridge(), force_terminal=True, color_system="auto")
        self.findings: List[AuditFinding] = []
        self.checks: List[Tuple[str, Callable]] = self._discover_checks()

    class AuditorContext:
        """A simple container for shared state that all checks can access."""
        def __init__(self, repo_root):
            """Initializes the shared context for all audit checks."""
            self.repo_root = repo_root
            self.intent_dir = self.repo_root / ".intent"
            self.src_dir = self.repo_root / "src"
            self.intent_model = IntentModel(self.repo_root)
            self.project_manifest = load_config(self.intent_dir / "project_manifest.yaml", "yaml")
            self.knowledge_graph = load_config(self.intent_dir / "knowledge/knowledge_graph.json", "json")
            self.symbols_map = self.knowledge_graph.get("symbols", {})
            self.symbols_list = list(self.symbols_map.values())
            self.load_config = load_config

    def _discover_checks(self) -> List[Tuple[str, Callable]]:
        """Dynamically discovers check methods from modules in the 'checks' directory."""
        discovered_checks = []
        checks_dir = Path(__file__).parent / "checks"
        
        for check_file in checks_dir.glob("*.py"):
            if check_file.name.startswith("__"): continue
            
            module_name = f"system.governance.checks.{check_file.stem}"
            try:
                module = importlib.import_module(module_name)
                for class_name, Class in inspect.getmembers(module, inspect.isclass):
                    if not class_name.endswith("Checks"):
                        continue

                    check_instance = Class(self.context)
                    for method_name, method in inspect.getmembers(check_instance, inspect.ismethod):
                        if method_name.startswith("_"): continue
                        
                        symbol_key = f"src/system/governance/checks/{check_file.name}::{method_name}"
                        symbol_data = self.context.symbols_map.get(symbol_key, {})
                        if symbol_data.get("capability", "").startswith("audit.check."):
                            check_name = symbol_data.get("intent", method_name)
                            discovered_checks.append((check_name, method))
            except ImportError as e:
                log.error(f"Failed to import check module {module_name}: {e}")

        log.debug(f"Discovered {len(discovered_checks)} audit checks.")
        discovered_checks.sort(key=lambda item: item[0] != "Ensures all implemented capabilities are valid.")
        return discovered_checks

    def run_full_audit(self) -> bool:
        """Run all discovered validation phases and return overall status."""
        self.console.print(Panel("🧠 CORE Constitutional Integrity Audit", style="bold blue", expand=False))
        
        for name, check_fn in self.checks:
            log.info(f"🔍 [bold]Running Check:[/bold] {name}")
            try:
                findings = check_fn()
                if findings:
                    self.findings.extend(findings)
                    for finding in findings:
                        if finding.severity == AuditSeverity.ERROR: log.error(f"❌ {finding.message}")
                        elif finding.severity == AuditSeverity.WARNING: log.warning(f"⚠️ {finding.message}")
                        elif finding.severity == AuditSeverity.SUCCESS: log.info(f"✅ {finding.message}")
            except Exception as e:
                log.error(f"💥 Check '{name}' failed with an unexpected error: {e}", exc_info=True)
                self.findings.append(AuditFinding(AuditSeverity.ERROR, f"Check failed: {e}", name))
        
        all_passed = not any(f.severity == AuditSeverity.ERROR for f in self.findings)
        self._report_final_status(all_passed)
        return all_passed

    def _report_final_status(self, passed: bool):
        """Prints the final audit summary to the console."""
        errors = [f for f in self.findings if f.severity == AuditSeverity.ERROR]
        warnings = [f for f in self.findings if f.severity == AuditSeverity.WARNING]

        if passed:
            msg = f"✅ ALL CHECKS PASSED ({len(warnings)} warnings)"
            self.console.print(Panel(msg, style="bold green", expand=False))
        else:
            msg = f"❌ AUDIT FAILED: {len(errors)} error(s) and {len(warnings)} warning(s) found."
            self.console.print(Panel(msg, style="bold red", expand=False))
        if errors:
            error_table = Table("🚨 Critical Errors", style="red", show_header=True, header_style="bold red")
            for err in errors: error_table.add_row(err.message)
            self.console.print(error_table)
        if warnings:
            warning_table = Table("⚠️ Warnings", style="yellow", show_header=True, header_style="bold yellow")
            for warn in warnings: warning_table.add_row(warn.message)
            self.console.print(warning_table)

def main():
    """CLI entry point for the Constitutional Auditor."""
    load_dotenv()
    auditor = ConstitutionalAuditor()
    try:
        success = auditor.run_full_audit()
        sys.exit(0 if success else 1)
    except FileNotFoundError as e:
        log.error(f"A required file was not found: {e}. Try running the introspection cycle.", exc_info=True)
        sys.exit(1)
    except Exception as e:
        log.error(f"An unexpected error occurred during the audit: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
