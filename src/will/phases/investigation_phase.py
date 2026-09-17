# src/will/phases/investigation_phase.py

"""Investigation Phase — read-only execution of an investigation plan (#895 U2).

Implements the ``runtime.investigate`` stage. Each step of a validated plan is
executed against reconnaissance already gathered or a bounded read of the bound
target, and every observation becomes an InvestigationFinding.

WHAT THIS PHASE MUST NEVER DO, and why it structurally cannot:

- **Reach ActionExecutor.** Steps are dispatched to local handlers through a
  closed mapping, not to the action registry. There is no import of
  ActionExecutor here and no code path that builds an ActionResult.
- **Create a Proposal.** Nothing in this module imports or constructs one.
- **Write anything.** No handler opens a file for writing, and none imports
  FileHandler. The only filesystem access is a bounded read in inspect.path.

Those are properties of what this module imports, not promises in a docstring —
an added import is the thing a reviewer should look for.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.logger import getLogger
from shared.models.investigation_finding import InvestigationFinding
from shared.models.target_binding import evaluation_view
from shared.models.workflow_models import PhaseResult


if TYPE_CHECKING:
    from shared.context import CoreContext
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)

# A bounded read. An investigation reports on a target; it does not ingest it.
_MAX_INSPECT_BYTES: int = 64 * 1024


# ID: fe5c4ea6-6afb-456a-b229-a3932f24c144
class InvestigationPhase:
    """Execute a read-only investigation plan and emit structured findings."""

    def __init__(self, core_context: CoreContext):
        self.context = core_context

    # ID: d98f42cc-0352-4c58-8678-8aba783e25a9
    async def execute(self, context: WorkflowContext) -> PhaseResult:
        """Run each planned step read-only and collect findings.

        A plan that never arrived is distinct from a plan that produced nothing:
        the first is an apparatus failure, the second is a result. They are
        reported differently.
        """
        start = time.time()

        parse_data = context.results.get("parse") or {}
        plan = parse_data.get("investigation_plan")

        if not plan:
            return PhaseResult(
                name="runtime",
                ok=False,
                error=(
                    "UNAVAILABLE: no investigation plan reached runtime.investigate; "
                    "the evaluation examined nothing."
                ),
                duration_sec=time.time() - start,
            )

        recon = (parse_data.get("reconnaissance") or {}).get("raw") or {}
        target_root = self._target_root()

        findings: list[InvestigationFinding] = []
        unsupported: list[str] = []

        for step in plan:
            action = getattr(step, "action", None) or (
                step.get("action") if isinstance(step, dict) else None
            )
            params = getattr(step, "params", None) or (
                step.get("params") if isinstance(step, dict) else {}
            )
            handler = self._handlers().get(str(action))
            if handler is None:
                # The validator should have refused this already; if one reaches
                # here the apparatus is wrong, and saying so beats improvising.
                unsupported.append(str(action))
                continue
            findings.extend(handler(recon, dict(params or {}), target_root))

        logger.info(
            "INVESTIGATE: %d step(s) executed, %d finding(s), %d unsupported",
            len(plan),
            len(findings),
            len(unsupported),
        )

        data: dict[str, Any] = {
            "findings": [f.as_payload() for f in findings],
            "findings_count": len(findings),
            "steps_executed": len(plan) - len(unsupported),
        }
        if unsupported:
            data["unsupported_steps"] = sorted(set(unsupported))

        return PhaseResult(
            name="runtime",
            ok=not unsupported,
            error=(
                f"Investigation plan contained steps this phase cannot run: "
                f"{sorted(set(unsupported))}"
                if unsupported
                else ""
            ),
            data=data,
            duration_sec=time.time() - start,
        )

    def _target_root(self) -> Path | None:
        # Ruling M2: the same subject-only view reconnaissance used -- the
        # original snapshot when bound, never the execution copy.
        root, _scope = evaluation_view(self.context)
        return root

    def _handlers(self) -> dict[str, Any]:
        return {
            "inspect.layout": self._inspect_layout,
            "inspect.artifact_types": self._inspect_artifact_types,
            "inspect.unclassified": self._inspect_unclassified,
            "inspect.absences": self._inspect_absences,
            "inspect.path": self._inspect_path,
        }

    def _inspect_layout(
        self, recon: dict[str, Any], params: dict[str, Any], root: Path | None
    ) -> list[InvestigationFinding]:
        layout = recon.get("layout") or {}
        if not layout:
            return [
                InvestigationFinding(
                    path="",
                    scope="target",
                    category="layout",
                    statement="Reconnaissance recorded no directory layout for this target.",
                    evidence_refs=["reconnaissance.layout"],
                )
            ]
        return [
            InvestigationFinding(
                path="",
                scope="target",
                category="layout",
                statement=(
                    f"Target holds {recon.get('file_count', 0)} files across "
                    f"{len(layout)} directory prefixes."
                ),
                evidence_refs=["reconnaissance.layout", "reconnaissance.file_count"],
            )
        ]

    def _inspect_artifact_types(
        self, recon: dict[str, Any], params: dict[str, Any], root: Path | None
    ) -> list[InvestigationFinding]:
        present = recon.get("artifact_types_present") or {}
        if not present:
            return [
                InvestigationFinding(
                    path="",
                    scope="target",
                    category="artifact_types",
                    statement=(
                        "No file in the target matched any registered artifact "
                        "type's discovery globs."
                    ),
                    evidence_refs=["reconnaissance.artifact_types_present"],
                )
            ]
        return [
            InvestigationFinding(
                path="",
                scope="target",
                category="artifact_types",
                statement=f"Target presents governed artifact type {type_id!r} in {count} file(s).",
                evidence_refs=[f"reconnaissance.artifact_types_present.{type_id}"],
            )
            for type_id, count in sorted(present.items())
        ]

    def _inspect_unclassified(
        self, recon: dict[str, Any], params: dict[str, Any], root: Path | None
    ) -> list[InvestigationFinding]:
        suffixes = recon.get("unclassified_suffixes") or {}
        count = recon.get("unclassified_count", 0)
        return [
            InvestigationFinding(
                path="",
                scope="target",
                category="unclassified",
                statement=(
                    f"{count} file(s) matched no registered artifact type; "
                    f"most common suffixes: {sorted(suffixes)[:5] or 'none'}."
                ),
                evidence_refs=["reconnaissance.unclassified_suffixes"],
            )
        ]

    def _inspect_absences(
        self, recon: dict[str, Any], params: dict[str, Any], root: Path | None
    ) -> list[InvestigationFinding]:
        # Absences live beside the raw recon facts, not inside them; an empty
        # list here means "nothing was absent", which is itself a finding.
        return [
            InvestigationFinding(
                path="",
                scope="target",
                category="absence",
                statement=(
                    "Reconnaissance recorded its observed absences on the run "
                    "identity; see the goal_run unavailable records."
                ),
                evidence_refs=["goal_run.unavailable"],
            )
        ]

    def _inspect_path(
        self, recon: dict[str, Any], params: dict[str, Any], root: Path | None
    ) -> list[InvestigationFinding]:
        relative = str(params.get("path") or "").strip()
        if not relative:
            return [
                InvestigationFinding(
                    path="",
                    scope="target",
                    category="inspection",
                    statement="inspect.path was planned without a path parameter.",
                    evidence_refs=["investigation_plan"],
                    confidence=1.0,
                )
            ]

        if root is None:
            return [
                InvestigationFinding(
                    path=relative,
                    scope="file",
                    category="inspection",
                    statement="UNAVAILABLE: no bound target root to resolve this path against.",
                    evidence_refs=["investigation_plan"],
                )
            ]

        resolved = (root / relative).resolve()
        if not str(resolved).startswith(str(root.resolve())):
            return [
                InvestigationFinding(
                    path=relative,
                    scope="file",
                    category="inspection",
                    statement="Path resolves outside the bound target and was not read.",
                    evidence_refs=["investigation_plan"],
                )
            ]

        if not resolved.is_file():
            return [
                InvestigationFinding(
                    path=relative,
                    scope="file",
                    category="inspection",
                    statement="No file exists at this path in the target.",
                    evidence_refs=[relative],
                )
            ]

        size = resolved.stat().st_size
        text = resolved.read_text(encoding="utf-8", errors="replace")[
            :_MAX_INSPECT_BYTES
        ]
        return [
            InvestigationFinding(
                path=relative,
                scope="file",
                category="inspection",
                statement=(
                    f"File exists: {size} bytes, {text.count(chr(10)) + 1} line(s) "
                    f"read within the {_MAX_INSPECT_BYTES}-byte inspection bound."
                ),
                evidence_refs=[relative],
            )
        ]
