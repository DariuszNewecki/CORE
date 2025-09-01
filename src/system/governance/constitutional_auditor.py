# src/system/governance/constitutional_auditor.py
"""
Orchestrates the discovery and execution of modular integrity checks to validate system governance and constitutional compliance.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import io
import sys
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from core.intent_model import IntentModel
from shared.ast_utility import (
    FunctionCallVisitor,
    parse_metadata_comment,
)  # New imports
from shared.config_loader import load_config
from shared.logger import getLogger
from shared.path_utils import get_repo_root
from shared.utils.manifest_aggregator import aggregate_manifests
from system.governance.models import AuditFinding, AuditSeverity

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

    # CAPABILITY: system.governance.auditor.initialize
    def __init__(self, repo_root_override: Optional[Path] = None):
        """
        Initialize the auditor, loading configuration and knowledge files.

        Args:
            repo_root_override: If provided, use this directory as the repo root (used for canary validation).
        """
        self.repo_root: Path = repo_root_override or get_repo_root()
        self.console = Console(
            file=self._LoggingBridge(), force_terminal=True, color_system="auto"
        )
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
            self.knowledge_graph = load_config(
                self.intent_dir / "knowledge/knowledge_graph.json"
            )
            self.symbols_map: dict = self.knowledge_graph.get("symbols", {})
            self.symbols_list: list = list(self.symbols_map.values())
            self.load_config = load_config

    # CAPABILITY: audit.check.discovery
    def _discover_checks(self) -> List[Tuple[str, Callable[[], List[AuditFinding]]]]:
        """Discover check methods from modules in the 'checks' directory."""
        discovered_checks: List[Tuple[str, Callable[[], List[AuditFinding]]]] = []
        checks_dir = Path(__file__).parent / "checks"

        from .checks.proposal_loader import ProposalLoader
        from .checks.proposal_signature_checker import ProposalSignatureChecker
        from .checks.proposal_summarizer import ProposalSummarizer
        from .checks.proposal_validator import ProposalValidator

        proposals_dir = self.repo_root / ".intent" / "proposals"
        proposal_loader = ProposalLoader(proposals_dir, self.repo_root)
        proposal_validator = ProposalValidator(self.repo_root)
        proposal_signature_checker = ProposalSignatureChecker()
        proposal_summarizer = ProposalSummarizer(proposals_dir, self.repo_root)

        for check_file in checks_dir.glob("*.py"):
            if check_file.name.startswith("__"):
                continue

            module_name = f"system.governance.checks.{check_file.stem}"
            try:
                module = importlib.import_module(module_name)
                for class_name, class_obj in inspect.getmembers(
                    module, inspect.isclass
                ):
                    if not class_name.endswith("Checks"):
                        continue

                    if class_name == "ProposalChecks":
                        check_instance = class_obj(
                            loader=proposal_loader,
                            validator=proposal_validator,
                            signature_checker=proposal_signature_checker,
                            summarizer=proposal_summarizer,
                        )
                    else:
                        check_instance = class_obj(self.context)

                    for method_name, method in inspect.getmembers(
                        check_instance, inspect.ismethod
                    ):
                        if method_name.startswith("_"):
                            continue
                        if method_name == "check_for_dead_code":
                            log.warning(
                                "Skipping 'check_for_dead_code' check due to known false positives with CLI commands"
                            )
                            continue

                        symbol_key = f"src/system/governance/checks/{check_file.name}::{method_name}"
                        symbol_data = self.context.symbols_map.get(symbol_key, {})
                        if symbol_data.get("capability", "").startswith("audit.check."):
                            check_name = symbol_data.get("intent", method_name)
                            discovered_checks.append((check_name, method))
            except ImportError as e:
                log.error(
                    f"Failed to import check module {module_name}: {e}", exc_info=True
                )

        log.debug(f"Discovered {len(discovered_checks)} audit checks")
        discovered_checks.sort(key=lambda item: item[0].split(":")[0])
        return discovered_checks

    # CAPABILITY: audit.check.capability_tags
    def validate_capability_tags(self, file_path: Path) -> List[AuditFinding]:
        """Validates capability tags in a file using shared AST utilities."""
        findings = []
        try:
            source = file_path.read_text(encoding="utf-8")
            lines = source.splitlines()
            tree = ast.parse(source)

            for node in ast.iter_child_nodes(tree):
                metadata = parse_metadata_comment(node, lines)  # Use shared utility
                if metadata.get("capability") == "unassigned":
                    findings.append(
                        AuditFinding(
                            severity=AuditSeverity.WARNING,
                            message=f"Unassigned capability tag in {node.name}",
                            check_name="capability_validation",
                            file_path=str(file_path),
                        )
                    )

                visitor = FunctionCallVisitor()  # Use shared visitor
                visitor.visit(node)
                # Optionally use visitor.calls for further checks (e.g., forbidden calls)

        except Exception as e:
            log.error(f"Error validating {file_path}: {e}")
            findings.append(
                AuditFinding(
                    severity=AuditSeverity.ERROR,
                    message=f"Failed to validate capability tags: {e}",
                    check_name="capability_validation",
                    file_path=str(file_path),
                )
            )

        return findings

    # CAPABILITY: audit.execute.full
    def run_full_audit(self) -> bool:
        """Run all discovered validation checks and return overall status."""
        self.console.print(
            Panel(
                "🧠 CORE Constitutional Integrity Audit",
                style="bold blue",
                expand=False,
            )
        )

        for check_name, check_fn in self.checks:
            short_name = check_name.split(":")[0]
            log.info(f"🔍 Running Check: {short_name}")
            try:
                findings = check_fn()
                if findings:
                    self.findings.extend(findings)
                    for finding in findings:
                        message = finding.message
                        if finding.file_path:
                            message += f" (in {finding.file_path})"

                        match finding.severity:
                            case AuditSeverity.ERROR:
                                log.error(f"❌ {message}")
                            case AuditSeverity.WARNING:
                                log.warning(f"⚠️ {message}")
                            case AuditSeverity.SUCCESS:
                                log.info(f"✅ {message}")
            except Exception as e:
                log.error(
                    f"💥 Check '{check_name}' failed unexpectedly: {e}", exc_info=True
                )
                self.findings.append(
                    AuditFinding(
                        severity=AuditSeverity.ERROR,
                        message=f"Check failed: {e}",
                        check_name=check_name,
                    )
                )

        all_passed = not any(f.severity == AuditSeverity.ERROR for f in self.findings)

        from system.governance.audit_execution import AuditExecutor

        executor = AuditExecutor(self.context)
        executor.report_final_status(
            self.findings, all_passed, self.context.symbols_list
        )

        return all_passed


# CAPABILITY: governance.cli.run_constitutional_audit
def main() -> None:
    """CLI entry point for the Constitutional Auditor."""
    load_dotenv()
    auditor = ConstitutionalAuditor()
    try:
        success = auditor.run_full_audit()
        sys.exit(0 if success else 1)
    except FileNotFoundError as e:
        log.error(
            f"Required file not found: {e}. Try running the introspection cycle.",
            exc_info=True,
        )
        sys.exit(1)
    except Exception as e:
        log.error(f"Unexpected error during audit: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
