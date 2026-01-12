# src/body/cli/workflows/dev_sync_phases.py
"""
Dev sync workflow phase execution.

Coordinates execution of dev-sync phases through specialized phase executors.
Each phase is handled by a dedicated class for better modularity and testability.
"""

from __future__ import annotations

from typing import Any

from rich.console import Console

from body.cli.workflows.dev_sync_reporter import DevSyncReporter
from body.cli.workflows.phases import (
    CodeAnalysisPhase,
    CodeFixersPhase,
    DatabaseSyncPhase,
    QualityChecksPhase,
    VectorizationPhase,
)
from shared.context import CoreContext


# ID: 1d7f96e0-3fc3-4453-ae6b-e42aa17504b9
class DevSyncPhases:
    """Coordinates dev-sync workflow phases with proper error handling and reporting."""

    def __init__(
        self,
        core_context: CoreContext,
        reporter: DevSyncReporter,
        console: Console,
        write: bool,
        dry_run: bool,
        session_factory: Any,  # get_session callable
    ):
        self.core_context = core_context
        self.reporter = reporter
        self.console = console
        self.write = write
        self.dry_run = dry_run
        self.session_factory = session_factory

        # Initialize phase executors
        self.code_fixers = CodeFixersPhase(
            core_context=core_context,
            reporter=reporter,
            console=console,
            write=write,
            dry_run=dry_run,
        )

        self.quality_checks = QualityChecksPhase(
            reporter=reporter,
            console=console,
        )

        self.database_sync = DatabaseSyncPhase(
            core_context=core_context,
            reporter=reporter,
            console=console,
            dry_run=dry_run,
            session_factory=session_factory,
        )

        self.vectorization = VectorizationPhase(
            core_context=core_context,
            reporter=reporter,
            console=console,
            dry_run=dry_run,
            session_factory=session_factory,
        )

        self.code_analysis = CodeAnalysisPhase(
            core_context=core_context,
            reporter=reporter,
            console=console,
        )

    # ID: b2a2a398-5ba9-4779-ad8d-32e1ccd1d7ef
    def has_critical_failures(self) -> bool:
        """Check if any critical failures occurred."""
        non_critical = {
            "check.lint",
            "manage.define-symbols",
            "inspect.duplicates",
            "manage.vectors.sync",
            "fix.logging",
        }

        for phase in self.reporter.phases:
            for result in phase.results:
                if not result.ok and result.action_id not in non_critical:
                    return True
        return False

    # =========================================================================
    # PHASE 1: CODE FIXERS
    # =========================================================================

    # ID: 62bb1514-6702-40b0-bc18-1fce5d2852fd
    async def run_code_fixers(self) -> None:
        """Execute code fixing phase."""
        await self.code_fixers.execute()

    # =========================================================================
    # PHASE 2: QUALITY CHECKS
    # =========================================================================

    # ID: eb2ce29a-50cd-44f2-ac8e-a07c0581278d
    async def run_quality_checks(self) -> None:
        """Execute quality checking phase."""
        await self.quality_checks.execute()

    # =========================================================================
    # PHASE 4: DATABASE SYNC
    # =========================================================================

    # ID: 7c8d9e0f-1a2b-3c4d-5e6f-7a8b9c0d1e2f
    async def run_database_sync(self) -> None:
        """Execute database synchronization phase."""
        await self.database_sync.execute()

    # =========================================================================
    # PHASE 5: VECTORIZATION
    # =========================================================================

    # ID: 9b697ab9-f6b1-484c-9569-3395dc7aad0f
    async def run_vectorization(self) -> None:
        """Execute vectorization phase."""
        await self.vectorization.execute()

    # =========================================================================
    # PHASE 6: CODE ANALYSIS
    # =========================================================================

    # ID: 4e6cbfc4-7ce7-4adc-980d-90c315da8123
    async def run_code_analysis(self) -> None:
        """Execute code analysis phase."""
        await self.code_analysis.execute()
