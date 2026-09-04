# tests/mind/logic/engines/workflow_gate/test_g2_workflow_gate_rules.py

"""#842 Unit I: the 3 workflow_gate blocking rules.

Every fixture pair below was run against the real
``WorkflowGateEngine``/``WorkflowCheck`` dispatch chain (never mocked at
the check level) with live params loaded from the actual
``.intent/enforcement/mappings/`` YAML, and each pins CURRENT, CONFIRMED
production behavior.

quality.type_safety -- VERIFIED (#847 fixed). Its mypy_check mechanism
genuinely works when mypy is present (confirmed below: a real type error
produces a real BLOCK-shaped finding, real clean code produces none), and
the dependency-absence path (confirmed below via the real engine, live
mapping params) now surfaces one ENFORCEMENT_UNAVAILABLE finding instead
of silently reporting compliant -- the audit-verdict policy
(.intent/enforcement/config/audit_verdict.yaml,
any_blocking_unavailable_rules) routes that to DEGRADED, never PASS.
See tests/mind/governance/test_auditor___determine_verdict.py for the
verdict-level proof through the real ``execute_rule``/``_determine_verdict``
path.

code.imports.must_resolve / code.imports.no_stale_namespace -- VERIFIED
(#855 fixed). ImportResolutionCheck.verify() now reads its mapping's
``params["tools"]`` and runs whatever is declared instead of one
hardcoded ``ruff --select F821,F401`` regardless of which rule fired.
The mapping itself also needed a governor-applied correction (this was
not a code-only fix): the declared mypy args
(``--ignore-missing-imports=false``) were an argparse usage error on
mypy 1.18.2 (a store_true flag rejects an explicit value) -- invisible
until now because the dead-params bug meant they had never actually
been executed -- and no_stale_namespace's ruff-only mechanism was
structurally incapable of import resolution at all (ruff's F821 verifies
that a *used name* is bound, not that an imported module exists, so it
cannot see this error class regardless of filter string). Both are now
mypy-backed (import-not-found), with no_stale_namespace narrowed via a
``filter_all`` (AND-semantics) list to the retired ``features.*``
namespace specifically -- see .intent/enforcement/mappings/code/imports.yaml
for the full rationale.

``WorkflowGateEngine._always_context_level = True`` still means the real
dispatch path (``verify_context``) always calls
``check_logic.verify(None, params)`` -- ``file_path`` is unconditionally
``None``, so ``target`` always resolves to the literal string ``"src"``,
independent of the mapping's ``scope.applies_to``/``excludes``. That
engine-level fact predates #855 and is unchanged by it; it is tracked
separately as #869 (not fixed here).

Tool-absence handling changed too: a missing declared tool (ruff or
mypy) now surfaces one aggregated ENFORCEMENT_UNAVAILABLE finding
instead of silently returning ``[]`` -- same G9 fix #847 made for
QualityGateCheck, now applied to ImportResolutionCheck.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from mind.governance.audit_context import AuditorContext
from mind.logic.engines.workflow_gate.base_check import StructuredViolation
from mind.logic.engines.workflow_gate.checks.import_resolution import (
    ImportResolutionCheck,
)
from mind.logic.engines.workflow_gate.checks.quality import QualityGateCheck
from mind.logic.engines.workflow_gate.engine import WorkflowGateEngine


_REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent
_MAPPINGS = _REPO_ROOT / ".intent" / "enforcement" / "mappings"


def _load_rule_params(mapping_rel: str, rule_id: str) -> dict:
    """Read the engine params for rule_id from a mappings YAML."""
    path = _MAPPINGS / mapping_rel
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["mappings"][rule_id]["params"]


def _as_str(violation: str | StructuredViolation) -> str:
    """Narrow the check's `str | StructuredViolation` union for assertions
    on fixtures that only ever produce plain-string violations."""
    assert isinstance(violation, str), f"expected a plain string, got {violation!r}"
    return violation


async def _run_via_real_engine(params: dict) -> list:
    """Drive the real WorkflowGateEngine.verify_context -- the actual
    production dispatch path for every workflow_gate rule."""
    path_resolver = MagicMock()
    path_resolver.repo_root = _REPO_ROOT
    path_resolver.src_root = str(_REPO_ROOT / "src")
    engine = WorkflowGateEngine(path_resolver=path_resolver)
    context = AuditorContext(repo_path=_REPO_ROOT)
    return await engine.verify_context(context, params)


# ---------------------------------------------------------------------------
# code.imports.must_resolve / code.imports.no_stale_namespace -- VERIFIED,
# #855 fixed (mapping corrected by the governor in the same change).
# ---------------------------------------------------------------------------


async def test_must_resolve_verify_context_always_targets_src() -> None:
    """#869 (engine-level, unchanged by #855): the real dispatch path never
    targets a specific file -- every declared tool's subprocess is invoked
    with the literal string "src" as its final positional argument,
    proven by capturing every actual subprocess argv through the real
    engine. must_resolve declares two tools (ruff, mypy); both must show
    this, not just the first one dispatched."""
    calls: list[tuple] = []

    async def fake_exec(*args, **kwargs):
        calls.append(args)
        proc = MagicMock()

        async def _communicate():
            return (b"", b"")

        proc.communicate = _communicate
        proc.returncode = 0
        return proc

    params = _load_rule_params("code/imports.yaml", "code.imports.must_resolve")
    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        await _run_via_real_engine(params)

    assert len(calls) == 2, f"expected ruff + mypy dispatch, got {calls}"
    for call_args in calls:
        assert call_args[-1] == "src", f"target was not 'src' in {call_args}"


async def test_must_resolve_fires_on_genuine_unresolvable_import(
    tmp_path: Path,
) -> None:
    """#855 D-b fixed: with an explicit isolated file_path (bypassing the
    verify_context discard proven above) and the rule's live mapping
    params, a textbook-unresolvable import now produces a real BLOCK-shaped
    finding -- mypy's import-not-found, not ruff's F821/F401 (which still
    cannot see this error class and correctly contributes nothing)."""
    bad = tmp_path / "bad.py"
    bad.write_text(
        "import this_module_does_not_exist_anywhere_xyz\n"
        "x = this_module_does_not_exist_anywhere_xyz.foo()\n",
        encoding="utf-8",
    )
    params = _load_rule_params("code/imports.yaml", "code.imports.must_resolve")
    check = ImportResolutionCheck()
    result = await check.verify(bad, params)
    assert len(result) == 1
    violation = _as_str(result[0])
    assert "import-not-found" in violation
    assert "this_module_does_not_exist_anywhere_xyz" in violation


async def test_must_resolve_produces_zero_findings_for_resolvable_import(
    tmp_path: Path,
) -> None:
    """Compliant fixture: a file whose only import genuinely resolves
    produces zero findings through the same live-mapping path."""
    clean = tmp_path / "clean.py"
    clean.write_text("import os\n\nprint(os.getcwd())\n", encoding="utf-8")
    params = _load_rule_params("code/imports.yaml", "code.imports.must_resolve")
    check = ImportResolutionCheck()
    result = await check.verify(clean, params)
    assert result == []


async def test_no_stale_namespace_fires_on_stale_features_reference(
    tmp_path: Path,
) -> None:
    """#855 D-b fixed for the second rule: a textbook stale-namespace
    import (the retired features.* namespace) now produces a real finding
    via the rule's live mapping params (mypy + filter_all)."""
    stale = tmp_path / "stale.py"
    stale.write_text(
        "from features.old_module import legacy_thing\nx = legacy_thing()\n",
        encoding="utf-8",
    )
    params = _load_rule_params("code/imports.yaml", "code.imports.no_stale_namespace")
    check = ImportResolutionCheck()
    result = await check.verify(stale, params)
    assert len(result) == 1
    violation = _as_str(result[0])
    assert "import-not-found" in violation
    assert "features.old_module" in violation


async def test_no_stale_namespace_produces_zero_findings_for_resolvable_import(
    tmp_path: Path,
) -> None:
    clean = tmp_path / "clean.py"
    clean.write_text("import os\n\nprint(os.getcwd())\n", encoding="utf-8")
    params = _load_rule_params("code/imports.yaml", "code.imports.no_stale_namespace")
    check = ImportResolutionCheck()
    result = await check.verify(clean, params)
    assert result == []


async def test_must_resolve_and_no_stale_namespace_are_no_longer_identical(
    tmp_path: Path,
) -> None:
    """#855 D-a fixed: before this fix both rules dispatched to one
    hardcoded ruff invocation and were functionally identical. Now, a
    genuinely unresolvable import OUTSIDE the retired features.* namespace
    fires must_resolve but not no_stale_namespace -- the two rules
    demonstrably differ in what they fire on."""
    bad = tmp_path / "bad.py"
    bad.write_text(
        "import this_module_does_not_exist_anywhere_xyz\n"
        "x = this_module_does_not_exist_anywhere_xyz.foo()\n",
        encoding="utf-8",
    )
    must_resolve_params = _load_rule_params(
        "code/imports.yaml", "code.imports.must_resolve"
    )
    no_stale_params = _load_rule_params(
        "code/imports.yaml", "code.imports.no_stale_namespace"
    )
    check = ImportResolutionCheck()

    must_resolve_result = await check.verify(bad, must_resolve_params)
    no_stale_result = await check.verify(bad, no_stale_params)

    assert len(must_resolve_result) == 1
    assert no_stale_result == []


async def test_must_resolve_surfaces_unavailable_when_ruff_missing_via_real_engine() -> (
    None
):
    """#855 D-d fixed: a missing declared tool (ruff, the first of
    must_resolve's two declared tools) now surfaces one aggregated
    ENFORCEMENT_UNAVAILABLE finding through the real production dispatch
    path with live mapping params, instead of silently returning []. Same
    G9 shape #847 fixed for QualityGateCheck, proven here for
    ImportResolutionCheck (not covered by #847's scope)."""
    params = _load_rule_params("code/imports.yaml", "code.imports.must_resolve")
    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=FileNotFoundError(2, "No such file or directory", "ruff"),
    ):
        result = await _run_via_real_engine(params)
    assert len(result) == 1
    assert result[0].context["finding_type"] == "ENFORCEMENT_UNAVAILABLE"
    assert result[0].context["reason"] == "tool_not_installed"
    assert result[0].context["tool"] == "ruff"


async def test_no_stale_namespace_surfaces_unavailable_when_mypy_missing_via_real_engine() -> (
    None
):
    """Same proof for no_stale_namespace, whose sole declared tool is mypy."""
    params = _load_rule_params("code/imports.yaml", "code.imports.no_stale_namespace")
    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=FileNotFoundError(2, "No such file or directory", "mypy"),
    ):
        result = await _run_via_real_engine(params)
    assert len(result) == 1
    assert result[0].context["finding_type"] == "ENFORCEMENT_UNAVAILABLE"
    assert result[0].context["reason"] == "tool_not_installed"
    assert result[0].context["tool"] == "mypy"


# ---------------------------------------------------------------------------
# quality.type_safety -- gap, #847 (existing; not duplicated)
# ---------------------------------------------------------------------------


async def test_type_safety_fires_on_a_genuine_type_error(tmp_path: Path) -> None:
    """The mypy_check mechanism itself works when the tool is present --
    real mypy, real subprocess, real BLOCK-shaped StructuredViolation for
    a genuine type error. Confirms quality.type_safety's defect is
    narrower than the two code.imports rows: only dependency-absence is
    broken (below), not the underlying mechanism."""
    (tmp_path / "bad_types.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n\nadd('x', 'y')\n",
        encoding="utf-8",
    )
    path_resolver = MagicMock()
    path_resolver.repo_root = tmp_path
    check = QualityGateCheck(
        path_resolver, "mypy_check", ["mypy", "bad_types.py", "--no-error-summary"]
    )
    result = await check.verify(None, {})
    assert len(result) == 1
    assert "type error" in result[0].message
    assert result[0].context["tool"] == "mypy"


async def test_type_safety_passes_for_correctly_typed_code(tmp_path: Path) -> None:
    (tmp_path / "good_types.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n\nadd(1, 2)\n",
        encoding="utf-8",
    )
    path_resolver = MagicMock()
    path_resolver.repo_root = tmp_path
    check = QualityGateCheck(
        path_resolver, "mypy_check", ["mypy", "good_types.py", "--no-error-summary"]
    )
    result = await check.verify(None, {})
    assert result == []


async def test_type_safety_surfaces_unavailable_when_mypy_absent_via_real_engine() -> (
    None
):
    """#847 fix, proven through the real WorkflowGateEngine.verify_context
    (not just QualityGateCheck in isolation, which
    test_tool_absence_silent_skip.py already covers) -- a blocking rule's
    real production dispatch path, with the rule's live mapping params,
    now returns one ENFORCEMENT_UNAVAILABLE finding rather than an empty
    (compliant) list when its required tool is unavailable."""
    params = _load_rule_params(
        "architecture/quality_gates.yaml", "quality.type_safety"
    )
    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=FileNotFoundError(2, "No such file or directory", "mypy"),
    ):
        result = await _run_via_real_engine(params)
    assert len(result) == 1
    assert result[0].context["finding_type"] == "ENFORCEMENT_UNAVAILABLE"
    assert result[0].context["reason"] == "tool_not_installed"
    assert result[0].context["tool"] == "mypy"
