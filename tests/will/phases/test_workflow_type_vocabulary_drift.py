# tests/will/phases/test_workflow_type_vocabulary_drift.py

"""Drift guard for the three hardcoded workflow-type vocabularies.

`cli.runtime_external_run._WORKFLOW_TYPES` is what an operator can ask for;
`will.phases.interpret_phase._VALID_WORKFLOW_TYPES` is what INTERPRET accepts
explicitly; `will.phases.runtime_phase._WORKFLOW_ROUTING` is what RUNTIME can
dispatch. A type present in the first and absent from either of the others
is a run that fails after binding, probes and seeding -- exactly what the
2026-09-17 cold run against a disposable target hit (`evaluation` was in the
route and in RUNTIME routing but not in INTERPRET's set, added by #895 U2/U3
in two of the three places). Every offered type must also have a declared
workflow definition in ``.intent/workflows/definitions/``.
"""

from __future__ import annotations

from pathlib import Path

from cli.runtime_external_run import _WORKFLOW_TYPES as ROUTE_TYPES
from will.phases.interpret_phase import _VALID_WORKFLOW_TYPES as INTERPRET_TYPES
from will.phases.runtime_phase import _WORKFLOW_ROUTING as RUNTIME_ROUTING


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_every_route_workflow_type_is_accepted_by_interpret() -> None:
    missing = set(ROUTE_TYPES) - set(INTERPRET_TYPES)
    assert not missing, f"route offers types INTERPRET rejects: {sorted(missing)}"


def test_every_route_workflow_type_is_routed_by_runtime() -> None:
    missing = set(ROUTE_TYPES) - set(RUNTIME_ROUTING)
    assert not missing, f"route offers types RUNTIME cannot dispatch: {sorted(missing)}"


def test_every_route_workflow_type_has_a_declared_definition() -> None:
    definitions = REPO_ROOT / ".intent" / "workflows" / "definitions"
    declared = {p.stem for p in definitions.glob("*.yaml")}
    missing = set(ROUTE_TYPES) - declared
    assert not missing, f"route offers undeclared workflow types: {sorted(missing)}"
