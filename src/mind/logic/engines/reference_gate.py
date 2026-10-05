# src/mind/logic/engines/reference_gate.py

"""
Reference Gate Engine — governance references must resolve.

Hosts one context-level check, ``intent_references_resolve``: concrete
references that ``.intent/`` declares to code, files, or actions must point
at something that exists. A retirement or rename that leaves one behind is
residue the runtime otherwise meets only as a skipped flow step, a capped
test-generation lineage for a deleted file, or an orphan check rooted at a
missing entry point.

Field-aware by design — only fields whose meaning is "this must exist now":

- flow steps with ``kind: action`` → an ``@atomic_action(action_id=...)``
  decoration in ``src/``;
- ``enforcement/config/test_coverage.yaml`` ``include_files`` → files;
- any enforcement mapping's ``params.entry_points`` → files or directories;
- worker declarations' ``implementation.module`` / ``implementation.class``
  → a module under ``src/`` defining that class;
- ``governance/namespace_manifest.yaml`` classification ``path`` under
  ``.intent/`` → files (other trees may hold gitignored, machine-local
  documents such as ``.specs/core-ng/``, whose absence is not residue);
- ``enforcement/remediation/auto_remediation.yaml`` ACTIVE and DELEGATE
  entries → an ``@register_action`` id under ``src/body/atomic/``
  (``action:``) or an active flow's ``flow_id`` (``flow:``). PENDING
  entries name actions not yet built, by declaration, and are exempt (#935).

Globs, output locations, exclude lists and prose are deliberately out of
scope: their existence is not part of their meaning.

CONSTITUTIONAL ALIGNMENT:
- Read-only; ``.intent/`` is read through ``IntentRepository``.
- Deterministic verdict (ADR-113 PROVEN); one finding per dangling reference,
  attributed to the declaring ``.intent/`` file and field.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.infrastructure.intent.intent_repository import IntentRepository
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity
from shared.path_resolver import PathResolver

from .artifact_gate import _extract_register_action_remediates
from .base import BaseEngine, EngineResult, EvidenceClass
from .taxonomy_gate import _collect_atomic_action_ids


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)

CORE_ROLE = "facade"  # ADR-095 D3

_CHECK = "intent_references_resolve"
_CHECK_ID = "architecture.intent.references_resolve"
_TEST_COVERAGE_REL = "enforcement/config/test_coverage.yaml"
_NAMESPACE_MANIFEST_REL = "governance/namespace_manifest.yaml"
_REMEDIATION_MAP_REL = "enforcement/remediation/auto_remediation.yaml"
_BODY_ATOMIC_REL = "src/body/atomic"
# Statuses whose target is routed (ACTIVE: proposals; DELEGATE: governor
# inbox). PENDING is "action does not yet exist in registry" by declaration.
_ROUTED_STATUSES = frozenset({"ACTIVE", "DELEGATE"})


# ID: 44e4ff98-ccc1-46a8-b11d-69d158680e4c
class ReferenceGateEngine(BaseEngine):
    """Context-level auditor: concrete ``.intent/`` references resolve."""

    engine_id = "reference_gate"
    evidence_class = EvidenceClass.PROVEN

    @classmethod
    # ID: 65edc072-dd91-4a6c-a503-370e70550576
    def is_context_level_for(cls, check_type: str | None) -> bool:
        """The single check is a cross-artifact sweep, not per-file."""
        return check_type == _CHECK

    def __init__(self, path_resolver: PathResolver) -> None:
        self._path_resolver = path_resolver

    # ID: 02ee6348-572d-4640-9173-294dc3d3ec0a
    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        """Per-file dispatch is a mis-mapping for this engine; say so."""
        return EngineResult(
            ok=False,
            message=(
                f"reference_gate: check_type {params.get('check_type')!r} is "
                "context-level; dispatch via verify_context, not verify"
            ),
            violations=[],
            engine_id=self.engine_id,
        )

    # ID: 1a978b53-7691-45d9-829f-63ce81de6f12
    async def verify_context(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        """One finding per dangling reference across every covered field."""
        if params.get("check_type") != _CHECK:
            return [
                AuditFinding(
                    check_id="reference_gate.unknown_check_type",
                    severity=AuditSeverity.BLOCK,
                    message=(
                        f"reference_gate: unknown check_type "
                        f"{params.get('check_type')!r}; valid: {_CHECK!r}"
                    ),
                    file_path="none",
                )
            ]
        return find_dangling_references(Path(context.repo_path))


# ID: 830789ae-4ffc-451f-a55f-3b8e9c349e8c
def find_dangling_references(repo_root: Path) -> list[AuditFinding]:
    """Sweep every covered field under ``repo_root/.intent`` (public for tests)."""
    intent = IntentRepository(root=repo_root / ".intent", strict=False)
    dangling: list[tuple[Path, str, str, str]] = []
    dangling += _flow_action_refs(intent, repo_root)
    dangling += _test_coverage_files(intent, repo_root)
    dangling += _mapping_entry_points(intent, repo_root)
    dangling += _worker_implementations(intent, repo_root)
    dangling += _namespace_manifest_paths(intent, repo_root)
    dangling += _remediation_targets(intent, repo_root)
    return [
        AuditFinding(
            check_id=_CHECK_ID,
            severity=AuditSeverity.BLOCK,
            message=(
                f"{_rel(declaring, repo_root)}: {field} references "
                f"{value!r}, which {problem}. Update the reference to its "
                "successor or remove it."
            ),
            file_path=_rel(declaring, repo_root),
            context={"field": field, "reference": value},
        )
        for declaring, field, value, problem in dangling
    ]


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path)


def _flow_action_refs(
    intent: IntentRepository, repo_root: Path
) -> list[tuple[Path, str, str, str]]:
    action_ids = _collect_atomic_action_ids(repo_root / "src")
    out: list[tuple[Path, str, str, str]] = []
    for path, doc in intent.iter_flow_documents():
        steps = ((doc.get("flow") or {}).get("steps")) or []
        for step in steps:
            if not isinstance(step, dict) or step.get("kind") != "action":
                continue
            ref = step.get("ref_id")
            if isinstance(ref, str) and ref not in action_ids:
                out.append(
                    (path, "flow.steps[].ref_id", ref, "no @atomic_action declares")
                )
    return out


def _test_coverage_files(
    intent: IntentRepository, repo_root: Path
) -> list[tuple[Path, str, str, str]]:
    path = intent.resolve_rel(_TEST_COVERAGE_REL)
    if not path.exists():
        return []
    doc = intent.load_document(path)
    return [
        (path, "include_files", f, "does not exist")
        for f in doc.get("include_files") or []
        if isinstance(f, str) and not (repo_root / f).exists()
    ]


def _mapping_entry_points(
    intent: IntentRepository, repo_root: Path
) -> list[tuple[Path, str, str, str]]:
    out: list[tuple[Path, str, str, str]] = []
    for path, doc in intent.iter_documents(under="enforcement/mappings"):
        mappings = doc.get("mappings")
        if not isinstance(mappings, dict):
            continue
        for rule_id, mapping in mappings.items():
            params = (mapping or {}).get("params") or {}
            for ep in params.get("entry_points") or []:
                if isinstance(ep, str) and not (repo_root / ep).exists():
                    out.append(
                        (path, f"{rule_id}.params.entry_points", ep, "does not exist")
                    )
    return out


def _worker_implementations(
    intent: IntentRepository, repo_root: Path
) -> list[tuple[Path, str, str, str]]:
    out: list[tuple[Path, str, str, str]] = []
    for path, doc in intent.iter_documents(under="workers"):
        impl = doc.get("implementation")
        if not isinstance(impl, dict) or not isinstance(impl.get("module"), str):
            continue
        module = impl["module"]
        base = repo_root / "src" / Path(*module.split("."))
        source = base.with_suffix(".py")
        if not source.exists():
            source = base / "__init__.py"
        if not source.exists():
            out.append(
                (path, "implementation.module", module, "is not a module under src/")
            )
            continue
        cls = impl.get("class")
        if isinstance(cls, str) and cls not in _top_level_classes(source):
            out.append(
                (path, "implementation.class", cls, f"is not defined in {module}")
            )
    return out


def _top_level_classes(source: Path) -> set[str]:
    """Class names a module defines or re-exports (package ``__init__``
    re-exports such as ``from .worker import TestRemediatorWorker``)."""
    try:
        tree = ast.parse(source.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        logger.debug("reference_gate: cannot parse %s: %s", source, exc)
        return set()
    names = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
    return names


def _namespace_manifest_paths(
    intent: IntentRepository, repo_root: Path
) -> list[tuple[Path, str, str, str]]:
    path = intent.resolve_rel(_NAMESPACE_MANIFEST_REL)
    if not path.exists():
        return []
    doc = intent.load_document(path)
    return [
        (path, "classifications[].path", entry["path"], "does not exist")
        for entry in doc.get("classifications") or []
        if isinstance(entry, dict)
        and isinstance(entry.get("path"), str)
        and entry["path"].startswith(".intent/")
        and not (repo_root / entry["path"]).exists()
    ]


def _remediation_targets(
    intent: IntentRepository, repo_root: Path
) -> list[tuple[Path, str, str, str]]:
    path = intent.resolve_rel(_REMEDIATION_MAP_REL)
    if not path.exists():
        return []
    mappings = intent.load_document(path).get("mappings")
    if not isinstance(mappings, dict):
        return []
    # Same predicate dispatch and the ACTIVE-routing check use: an action
    # exists when body/atomic registers it, not merely when it is decorated.
    action_ids = set(_extract_register_action_remediates(repo_root / _BODY_ATOMIC_REL))
    flow_ids = _active_flow_ids(intent)
    out: list[tuple[Path, str, str, str]] = []
    for rule_id, entry in mappings.items():
        if not isinstance(entry, dict) or entry.get("status") not in _ROUTED_STATUSES:
            continue
        action = entry.get("action")
        if isinstance(action, str) and action not in action_ids:
            out.append(
                (
                    path,
                    f"mappings.{rule_id}.action",
                    action,
                    f"no @register_action declares in {_BODY_ATOMIC_REL}/",
                )
            )
        flow = entry.get("flow")
        if isinstance(flow, str) and flow not in flow_ids:
            out.append(
                (path, f"mappings.{rule_id}.flow", flow, "is not an active flow_id")
            )
    return out


def _active_flow_ids(intent: IntentRepository) -> set[str]:
    """flow_ids FlowRegistry would load (metadata.status defaults to active)."""
    ids: set[str] = set()
    for _path, doc in intent.iter_flow_documents():
        if (doc.get("metadata") or {}).get("status", "active") != "active":
            continue
        flow_id = (doc.get("flow") or {}).get("flow_id")
        if isinstance(flow_id, str):
            ids.add(flow_id)
    return ids
