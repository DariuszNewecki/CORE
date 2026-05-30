# src/mind/logic/engines/taxonomy_gate.py

"""
Taxonomy Gate Engine — operational-capability taxonomy invariants.

Single-check context-level engine that enforces ADR-079 D9's
phantom-decoration invariant: every capability id declared in
``.intent/taxonomies/operational_capabilities.yaml`` must be backed by
exactly one ``@atomic_action(action_id="<id>")`` decoration in ``src/``.

The check is cross-artifact (whole YAML against every src/ AST), which is why
this is its own engine rather than a per-file check under ``ast_gate``.
The substrate is the live YAML + decoration sweep, not a single file_path.

CONSTITUTIONAL ALIGNMENT:
- Async-first verify per the BaseEngine contract (ADR-076 D1/D2).
- Context-level dispatch for the one check_type it owns.
- Fail-soft on per-file parse errors (a single unparseable file must not
  crash the audit cycle — log and skip).
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from shared.infrastructure.intent.operational_capabilities import (
    OperationalCapabilityTaxonomyError,
    load_operational_capabilities,
)
from shared.logger import getLogger
from shared.path_resolver import PathResolver

from .base import BaseEngine, EngineResult


logger = getLogger(__name__)


_DECORATOR_BACKING_CHECK = "operational_capabilities_decorator_backing"


# ID: 8c4e1f7b-2d6a-4b58-9e3c-1a7f6d4b5e89
class TaxonomyGateEngine(BaseEngine):
    """Operational-capability taxonomy backing auditor.

    Implements ADR-079 D9's phantom-decoration invariant. A capability id
    in the YAML with no matching ``@atomic_action(action_id=<id>)``
    decoration in ``src/`` is a phantom — it cannot be authorized by the
    chokepoint because no caller can ever set ``_executor_token`` to it.

    Stage 1 ships at ``reporting`` enforcement (advisory). Stage 2 of
    ADR-079 D10 promotes to ``blocking`` together with the phantom
    resolution change-set (#495).
    """

    engine_id = "taxonomy_gate"

    @classmethod
    # ID: f3a8d672-5c19-4e2b-b481-6d9e7f3a2c14
    def is_context_level_for(cls, check_type: str | None) -> bool:
        """The decorator-backing check is cross-artifact, not per-file."""
        return check_type == _DECORATOR_BACKING_CHECK

    def __init__(self, path_resolver: PathResolver) -> None:
        """Initialize with the audit's path resolver — used for the repo-root
        anchor when locating the YAML and AST-walking ``src/``."""
        self._path_resolver = path_resolver

    # ID: 2b9d4f6a-8e3c-4751-a16d-5b9e2d7f4c83
    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        """Dispatch on ``check_type``; the context-level checks ignore ``file_path``."""
        check_type = params.get("check_type")
        if check_type == _DECORATOR_BACKING_CHECK:
            return self._check_decorator_backing()
        return EngineResult(
            ok=False,
            message=f"taxonomy_gate: unknown check_type {check_type!r}",
            violations=[],
            engine_id=self.engine_id,
        )

    def _check_decorator_backing(self) -> EngineResult:
        """Compute the YAML-vs-decoration set difference and emit one
        violation per phantom (capability id in YAML, absent in src/)."""
        repo_root = self._path_resolver.repo_root
        try:
            capabilities = load_operational_capabilities(repo_root)
        except OperationalCapabilityTaxonomyError as exc:
            # Loader failure is a degraded-instrument state, not a phantom
            # finding — surface it as engine-not-ok so the auditor reports
            # the underlying YAML defect rather than misattributing it.
            return EngineResult(
                ok=False,
                message=f"taxonomy_gate: cannot load operational-capability taxonomy: {exc}",
                violations=[],
                engine_id=self.engine_id,
            )

        yaml_ids = {cap.id for cap in capabilities}
        decoration_ids = _collect_atomic_action_ids(repo_root / "src")

        phantoms = sorted(yaml_ids - decoration_ids)
        if not phantoms:
            return EngineResult(
                ok=True,
                message=(
                    f"taxonomy_gate: all {len(yaml_ids)} capability id(s) have "
                    f"backing @atomic_action decorations in src/."
                ),
                violations=[],
                engine_id=self.engine_id,
            )

        violations: list[str | dict[str, Any]] = [
            (
                f"Phantom capability '{cap_id}' in "
                f".intent/taxonomies/operational_capabilities.yaml has no "
                f"matching @atomic_action(action_id={cap_id!r}) decoration "
                f"in src/. Resolve per ADR-079 D9: strip the YAML entry "
                f"(Shape 1) or decorate the underlying function and "
                f"re-route its dispatch through ActionExecutor.execute "
                f"(Shape 2 — three-change recipe: @register_action + "
                f"@atomic_action + **kwargs)."
            )
            for cap_id in phantoms
        ]
        return EngineResult(
            ok=False,
            message=(
                f"taxonomy_gate: {len(phantoms)} phantom capability id(s) in "
                f"operational_capabilities.yaml without @atomic_action backing"
            ),
            violations=violations,
            engine_id=self.engine_id,
        )


def _collect_atomic_action_ids(src_root: Path) -> set[str]:
    """AST-walk ``src/`` collecting action_id string-literal values from
    every ``@atomic_action(action_id=...)`` decoration.

    Skips files that cannot be parsed or read — a single broken file must
    not crash the audit. Skips decorations whose ``action_id`` is not a
    string literal (e.g. computed) — those cases are too rare in practice
    to silently grant backing credit; they appear as phantoms and the
    finding's resolution prompt clarifies the path forward.
    """
    found: set[str] = set()
    if not src_root.is_dir():
        return found
    for py in src_root.rglob("*.py"):
        try:
            source = py.read_text(encoding="utf-8")
        except OSError as exc:
            logger.debug("taxonomy_gate: cannot read %s: %s", py, exc)
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            logger.debug("taxonomy_gate: cannot parse %s: %s", py, exc)
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                action_id = _extract_action_id(dec)
                if action_id is not None:
                    found.add(action_id)
    return found


def _extract_action_id(decorator: ast.expr) -> str | None:
    """Return the ``action_id`` keyword value if ``decorator`` is a call to
    ``atomic_action`` with a string-literal ``action_id`` kwarg; else None.

    Accepts both bare (``@atomic_action(...)``) and attribute access
    (``@module.atomic_action(...)``) forms so the check tracks the decoration
    irrespective of import style.
    """
    if not isinstance(decorator, ast.Call):
        return None
    func = decorator.func
    if isinstance(func, ast.Name):
        name = func.id
    elif isinstance(func, ast.Attribute):
        name = func.attr
    else:
        return None
    if name != "atomic_action":
        return None
    for kw in decorator.keywords:
        if kw.arg != "action_id":
            continue
        value = kw.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
        return None
    return None
