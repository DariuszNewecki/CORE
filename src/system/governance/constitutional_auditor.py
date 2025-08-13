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
from pathlib import Path
from typing import List, Optional, Callable, Tuple
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from shared.path_utils import get_repo_root
from shared.config_loader import load_config
from core.intent_model import IntentModel
from shared.logger import getLogger
from system.governance.models import AuditFinding, AuditSeverity
from shared.utils.manifest_aggregator import aggregate_manifests

log = getLogger(__name__)

# CAPABILITY: alignment_checking
class ConstitutionalAuditor:
    """Orchestrates the discovery and execution of constitutional checks."""

    class _LoggingBridge(io.StringIO):
        """Redirects console output to the logger."""
        def write(self, s: str) -> None:
            """Redirects writes to the logger info stream."""
            if cleaned_s := s.strip():
                log.info(cleaned_s)

    def __init__(self, repo_root_override: Optional[Path] = None):
        """
        Initialize the auditor, loading configuration and knowledge files.

        Args:
            repo_root_override: If provided, use this directory as the repo root (used for canary validation).
        """
        self.repo_root: Path = repo_root_override or get_repo_root()
        self.console = Console(file=self._LoggingBridge(), force_terminal=True, color_system="auto")
        self.context = self.AuditorContext(self.repo_root)
        self.findings: List[AuditFinding] = []
        self.checks: List[Tuple[str, Callable[[], List[AuditFinding]]]] = []

        if repo_root_override:
            dotenv_path = self.repo_root / ".env"
            if dotenv_path.exists():
                load_dotenv(dotenv_path=dotenv_path, override=True)
                log.info(f"Loaded environment from {dotenv_path} for canary validation")

        self.checks = self._discover_checks()

    class AuditorContext:
        """Shared state container for audit checks."""
        def __init__(self, repo_root: Path):
            """Initialize context with repository paths and configurations."""
            self.repo_root: Path = repo_root
            self.intent_dir: Path = repo_root / ".intent"
            self.src_dir: Path = repo_root / "src"
            self.intent_model = IntentModel(repo_root)
            self.project_manifest = aggregate_manifests(repo_root)
            self.knowledge_graph = load_config(self.intent_dir / "knowledge/knowledge_graph.json", "json")
            self.symbols_map: dict = self.knowledge_graph.get("symbols", {})
            self.symbols_list: list = list(self.symbols_map.values())
            self.load_config = load_config

    def _discover_checks(self) -> List[Tuple[str, Callable[[], List[AuditFinding]]]]:
        """Discover check methods from modules in the 'checks' directory."""
        discovered_checks: List[Tuple[str, Callable[[], List[AuditFinding]]]] = []
        checks_dir = Path(__file__).parent / "checks"

        for check_file in checks_dir.glob("*.py"):
            if check_file.name.startswith("__"):
                continue

            module_name = f"system.governance.checks.{check_file.stem}"
            try:
                module = importlib.import_module(module_name)
                for class_name, class_obj in inspect.getmembers(module, inspect.isclass):
                    if not class_name.endswith("Checks"):
                        continue

                    check_instance = class_obj(self.context)
                    for method_name, method in inspect.getmembers(check_instance, inspect.ismethod):
                        if method_name.startswith("_"):
                            continue
                        if method_name == "check_for_dead_code":
                            log.warning(f"Skipping '{method_name}' check due to known false positives with CLI commands")
                            continue

                        symbol_key = f"src/system/governance/checks/{check_file.name}::{method_name}"
                        symbol_data = self.context.symbols_map.get(symbol_key, {})
                        if symbol_data.get("capability", "").startswith("audit.check."):
                            check_name = symbol_data.get("intent", method_name)
                            discovered_checks.append((check_name, method))
            except ImportError as e:
                log.error(f"Failed to import check module {module_name}: {e}", exc_info=True)

        log.debug(f"Discovered {len(discovered_checks)} audit checks")
        discovered_checks.sort(key=lambda item: item[0].split(":")[0])
        return discovered_checks

    def run_full_audit(self) -> bool:
        """Run all discovered validation checks and return overall status."""
        self.console.print(Panel("🧠 CORE Constitutional Integrity Audit", style="bold blue", expand=False))

        for check_name, check_fn in self.checks:
            short_name = check_name.split(":")[0]
            log.info(f"🔍 Running Check: {short_name}")
            try:
                findings = check_fn()
                if findings:
                    self.findings.extend(findings)
                    for finding in findings:
                        match finding.severity:
                            case AuditSeverity.ERROR:
                                log.error(f"❌ {finding.message}")
                            case AuditSeverity.WARNING:
                                log.warning(f"⚠️ {finding.message}")
                            case AuditSeverity.SUCCESS:
                                log.info(f"✅ {finding.message}")
            except Exception as e:
                log.error(f"💥 Check '{check_name}' failed unexpectedly: {e}", exc_info=True)
                self.findings.append(AuditFinding(
                    severity=AuditSeverity.ERROR,
                    message=f"Check failed: {e}",
                    check_name=check_name
                ))

        all_passed = not any(f.severity == AuditSeverity.ERROR for f in self.findings)
        self._report_final_status(all_passed)
        return all_passed

    def _report_final_status(self, passed: bool) -> None:
        """Print final audit summary to the console."""
        errors = sum(1 for f in self.findings if f.severity == AuditSeverity.ERROR)
        warnings = sum(1 for f in self.findings if f.severity == AuditSeverity.WARNING)

        if passed:
            msg = f"✅ ALL CHECKS PASSED ({warnings} warnings)"
            style = "bold green"
        else:
            msg = f"❌ AUDIT FAILED: {errors} error(s) and {warnings} warning(s) found"
            style = "bold red"

        self.console.print(Panel(msg, style=style, expand=False))

def main() -> None:
    """CLI entry point for the Constitutional Auditor."""
    load_dotenv()
    auditor = ConstitutionalAuditor()
    try:
        success = auditor.run_full_audit()
        sys.exit(0 if success else 1)
    except FileNotFoundError as e:
        log.error(f"Required file not found: {e}. Try running the introspection cycle.", exc_info=True)
        sys.exit(1)
    except Exception as e:
        log.error(f"Unexpected error during audit: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()