# src/system/governance/check_discovery.py
"""
Handles the discovery and instantiation of constitutional audit checks.

This module is responsible for dynamically discovering check modules, properly instantiating
check classes with their required dependencies, and preparing them for execution by the
Constitutional Auditor.
"""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import TYPE_CHECKING, Callable, List, Tuple

from shared.logger import getLogger
from system.governance.models import AuditFinding

if TYPE_CHECKING:
    from .constitutional_auditor import ConstitutionalAuditor

log = getLogger(__name__)


class CheckDiscovery:
    """Discovers and instantiates constitutional audit checks with proper dependency injection."""

    def __init__(self, context: ConstitutionalAuditor.AuditorContext, repo_root: Path):
        """
        Initialize the check discovery system.

        Args:
            context: The auditor context containing shared state and configurations.
            repo_root: Root directory of the repository.
        """
        self.context = context
        self.repo_root = repo_root
        self.checks_dir = Path(__file__).parent / "checks"

    def discover_checks(self) -> List[Tuple[str, Callable[[], List[AuditFinding]]]]:
        """
        Discover check methods from modules in the 'checks' directory.

        Returns:
            List of tuples containing check names and their callable methods.
        """
        discovered_checks: List[Tuple[str, Callable[[], List[AuditFinding]]]] = []

        # Initialize proposal-related dependencies once
        proposal_dependencies = self._initialize_proposal_dependencies()

        for check_file in self.checks_dir.glob("*.py"):
            if check_file.name.startswith("__"):
                continue

            checks_from_file = self._process_check_file(
                check_file, proposal_dependencies
            )
            discovered_checks.extend(checks_from_file)

        log.debug(f"Discovered {len(discovered_checks)} audit checks")
        discovered_checks.sort(key=lambda item: item[0].split(":")[0])
        return discovered_checks

    def _initialize_proposal_dependencies(self) -> dict:
        """
        Initialize proposal-related dependencies for dependency injection.

        Returns:
            Dictionary containing initialized proposal dependencies.
        """
        try:
            from .checks.proposal_loader import ProposalLoader
            from .checks.proposal_signature_checker import ProposalSignatureChecker
            from .checks.proposal_summarizer import ProposalSummarizer
            from .checks.proposal_validator import ProposalValidator

            proposals_dir = self.repo_root / ".intent" / "proposals"

            return {
                "loader": ProposalLoader(proposals_dir, self.repo_root),
                "validator": ProposalValidator(self.repo_root),
                "signature_checker": ProposalSignatureChecker(),
                "summarizer": ProposalSummarizer(proposals_dir, self.repo_root),
            }
        except ImportError as e:
            log.warning(f"Could not initialize proposal dependencies: {e}")
            return {}

    def _process_check_file(
        self, check_file: Path, proposal_dependencies: dict
    ) -> List[Tuple[str, Callable[[], List[AuditFinding]]]]:
        """
        Process a single check file and extract check methods.

        Args:
            check_file: Path to the check file to process.
            proposal_dependencies: Pre-initialized proposal dependencies.

        Returns:
            List of check methods found in the file.
        """
        checks_from_file: List[Tuple[str, Callable[[], List[AuditFinding]]]] = []
        module_name = f"system.governance.checks.{check_file.stem}"

        try:
            module = importlib.import_module(module_name)

            for class_name, class_obj in inspect.getmembers(module, inspect.isclass):
                if not class_name.endswith("Checks"):
                    continue

                check_instance = self._instantiate_check_class(
                    class_name, class_obj, proposal_dependencies
                )
                if check_instance is None:
                    continue

                check_methods = self._extract_check_methods(check_instance, check_file)
                checks_from_file.extend(check_methods)

        except ImportError as e:
            log.error(
                f"Failed to import check module {module_name}: {e}", exc_info=True
            )

        return checks_from_file

    def _instantiate_check_class(
        self, class_name: str, class_obj: type, proposal_dependencies: dict
    ):
        """
        Instantiate a check class with appropriate dependencies.

        Args:
            class_name: Name of the check class.
            class_obj: The check class object.
            proposal_dependencies: Pre-initialized proposal dependencies.

        Returns:
            Instantiated check class or None if instantiation failed.
        """
        try:
            # Special dependency injection for ProposalChecks
            if class_name == "ProposalChecks" and proposal_dependencies:
                return class_obj(**proposal_dependencies)
            else:
                return class_obj(self.context)
        except Exception as e:
            log.error(
                f"Failed to instantiate check class {class_name}: {e}", exc_info=True
            )
            return None

    def _extract_check_methods(
        self, check_instance, check_file: Path
    ) -> List[Tuple[str, Callable[[], List[AuditFinding]]]]:
        """
        Extract check methods from an instantiated check class.

        Args:
            check_instance: Instantiated check class.
            check_file: Path to the check file (for symbol lookup).

        Returns:
            List of tuples containing check names and methods.
        """
        check_methods: List[Tuple[str, Callable[[], List[AuditFinding]]]] = []

        for method_name, method in inspect.getmembers(check_instance, inspect.ismethod):
            if method_name.startswith("_"):
                continue

            # Skip known problematic checks
            if method_name == "check_for_dead_code":
                log.warning(
                    "Skipping 'check_for_dead_code' check due to known false positives with CLI commands"
                )
                continue

            # Look up the check method in the symbols map
            symbol_key = (
                f"src/system/governance/checks/{check_file.name}::{method_name}"
            )
            symbol_data = self.context.symbols_map.get(symbol_key, {})

            if symbol_data.get("capability", "").startswith("audit.check."):
                check_name = symbol_data.get("intent", method_name)
                check_methods.append((check_name, method))

        return check_methods
