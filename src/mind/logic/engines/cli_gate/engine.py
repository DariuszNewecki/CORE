# src/mind/logic/engines/cli_gate/engine.py

"""CLI Gate Engine.

Audits the Typer command registry as a single context-level surface.
Replaces the manual ``audit_cli_registry`` self-check path for the
seven registry-interrogating rules and adds source-AST verification of
``cli.discovery_strict`` against the CLI loader file.

CONSTITUTIONAL ALIGNMENT:
- All eight check_types are context-level (``is_context_level_for``
  returns True) — the substrate is the live Typer app, not a per-file
  walk, so the per-file dispatcher is never engaged.
- The Typer app import is deferred to ``verify_context`` so engine
  discovery at ``EngineRegistry.initialize`` time does NOT trigger the
  heavy module-level side effects in ``cli.admin_cli``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from mind.logic.engines.base import BaseEngine, EngineResult
from mind.logic.engines.cli_gate.base_check import CliCheck
from mind.logic.engines.cli_gate.checks import (
    AsyncExecutionCheck,
    DangerousExplicitCheck,
    DiscoveryStrictCheck,
    HelpRequiredCheck,
    NoDuplicatesCheck,
    NoLayerExposureCheck,
    ResourceFirstCheck,
    StandardVerbsCheck,
)
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity
from shared.path_resolver import PathResolver


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)

_CONTEXT_CHECK_TYPES: frozenset[str] = frozenset(
    {
        "resource_first",
        "no_layer_exposure",
        "standard_verbs",
        "dangerous_explicit",
        "async_execution",
        "discovery_strict",
        "help_required",
        "no_duplicates",
    }
)


# ID: dc55a68d-d7f9-4645-984a-c9c432c472d8
class CliGateEngine(BaseEngine):
    """Context-level auditor for the Typer command registry."""

    engine_id = "cli_gate"

    @classmethod
    # ID: 060dc0c2-6d54-4544-aaec-86e1ef978243
    def is_context_level_for(cls, check_type: str | None) -> bool:
        """All cli_gate check_types inspect the command registry or the
        CLI loader as a whole — none consume a single ``file_path``.
        """
        return check_type in _CONTEXT_CHECK_TYPES

    # ID: 31883c58-8573-48fa-b9c0-cb63c613f755
    def __init__(self, path_resolver: PathResolver) -> None:
        self._path_resolver = path_resolver

        check_instances: list[CliCheck] = [
            ResourceFirstCheck(),
            NoLayerExposureCheck(),
            StandardVerbsCheck(),
            DangerousExplicitCheck(),
            AsyncExecutionCheck(),
            HelpRequiredCheck(),
            NoDuplicatesCheck(),
            DiscoveryStrictCheck(path_resolver=path_resolver),
        ]

        self._checks: dict[str, CliCheck] = {
            check.check_type: check for check in check_instances
        }

        logger.debug(
            "CliGateEngine initialized with %d check types: %s",
            len(self._checks),
            ", ".join(sorted(self._checks.keys())),
        )

    # ID: 934d1396-88a7-4ccd-991f-c9f198bed27d
    async def verify_context(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        """Dispatch the requested check_type against the Typer command
        registry. The Typer app is imported lazily here, once per call,
        so engine discovery stays hermetic.
        """
        check_type = params.get("check_type")
        if not check_type:
            return [
                AuditFinding(
                    check_id="cli_gate.error",
                    severity=AuditSeverity.BLOCK,
                    message="Missing 'check_type' parameter in cli_gate mapping.",
                    file_path="none",
                )
            ]

        check_logic = self._checks.get(check_type)
        if not check_logic:
            return [
                AuditFinding(
                    check_id="cli_gate.error",
                    severity=AuditSeverity.BLOCK,
                    message=(
                        f"cli_gate has no implementation for check_type '{check_type}'"
                    ),
                    file_path="none",
                )
            ]

        try:
            commands = self._walk_registry()
        except Exception as exc:
            logger.error(
                "cli_gate failed to walk Typer registry: %s", exc, exc_info=True
            )
            return [
                AuditFinding(
                    check_id=f"cli_gate.{check_type}.error",
                    severity=AuditSeverity.BLOCK,
                    message=(
                        f"cli_gate could not introspect the Typer registry: {exc}"
                    ),
                    file_path="none",
                )
            ]

        try:
            return check_logic.verify(commands, params)
        except Exception as exc:
            logger.error(
                "cli_gate check '%s' failed: %s", check_type, exc, exc_info=True
            )
            return [
                AuditFinding(
                    check_id=f"cli_gate.{check_type}.error",
                    severity=AuditSeverity.BLOCK,
                    message=(f"Internal cli_gate error during {check_type}: {exc}"),
                    file_path="none",
                )
            ]

    # ID: df3b2825-4023-47f0-b55a-492f21ee2ba0
    def _walk_registry(self) -> list[dict[str, Any]]:
        """Lazily import the Typer app and walk it once.

        The import is deferred so that EngineRegistry's import-time
        discovery does not trigger ``cli.admin_cli``'s module-level
        ``create_core_context`` bootstrap. The first audit run pays
        the cost once; sys.modules caches the import for subsequent
        runs in the same process.

        Normalises ``cmd['file_path']`` to repo-relative before returning
        (#486). The raw walker emits absolute paths via ``inspect.getfile``,
        which other consumers (``self_check.py`` metascribe) rely on; the
        normalisation is local to this engine so finding subjects emitted
        downstream are repo-relative — matching every other engine and
        keeping ``ViolationRemediator``'s crate validator from rejecting
        cli_gate proposals.
        """
        from cli.admin_cli import app as main_app
        from shared.cli.app_introspection import walk_typer_app

        commands = walk_typer_app(main_app, include_missing_handlers=True)
        repo_root = self._path_resolver.repo_root
        for cmd in commands:
            fp = cmd.get("file_path")
            if not fp or fp in ("none", "unknown"):
                continue
            p = Path(fp)
            if not p.is_absolute():
                continue
            try:
                cmd["file_path"] = str(p.relative_to(repo_root))
            except ValueError:
                # Path outside the repo — leave as-is; downstream handles it.
                continue
        return commands

    # ID: 70dce438-c504-4819-8f1b-d4bdf3362cf6
    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        """Required by BaseEngine, never reached: every cli_gate
        check_type is context-level, so the rule executor dispatches
        through verify_context instead of iterating files.
        """
        return EngineResult(
            ok=True,
            message="cli_gate is context-level; per-file verify is not used.",
            violations=[],
            engine_id=self.engine_id,
        )
