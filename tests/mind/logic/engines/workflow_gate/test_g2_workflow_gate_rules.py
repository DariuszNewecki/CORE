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

code.imports.must_resolve / code.imports.no_stale_namespace -- gap, see
#855 (new issue filed by this unit). Both dispatch to the same
check_type, import_resolution_check
(``ImportResolutionCheck.verify()``), which:

1. Never reads its own mapping's ``params`` (documented in source as
   "currently unused") -- the declared secondary ``mypy`` tool for
   must_resolve and the ``filter: "features."`` narrowing for
   no_stale_namespace are both dead; the two rules are functionally
   identical at dispatch time.
2. Runs ``ruff --select F821,F401``, which does not perform import
   resolution at all -- confirmed empirically: a file with a
   textbook-unresolvable import, and a file with a textbook-stale
   ``features.*`` reference, both produce zero findings.
3. ``WorkflowGateEngine._always_context_level = True`` means the real
   dispatch path (``verify_context``) always calls
   ``check_logic.verify(None, params)`` -- ``file_path`` is
   unconditionally ``None``, so ``target = str(file_path) if file_path
   else "src"`` always resolves to the literal string ``"src"``. Real
   production runs one fixed ``ruff check src ...`` per audit,
   independent of the mapping's ``scope.applies_to``/``excludes``.
4. Also silent-skips (returns ``[]``) when ``ruff`` itself is absent --
   the same G9 shape as #847, on a different check class not covered
   by that issue.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from mind.governance.audit_context import AuditorContext
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
# code.imports.must_resolve / code.imports.no_stale_namespace -- gap, #855
# ---------------------------------------------------------------------------


async def test_must_resolve_verify_context_always_discards_file_path() -> None:
    """Pins #855 finding 3: the real dispatch path never targets a specific
    file -- it always shells out against the literal string "src", proven
    by capturing the actual subprocess argv through the real engine."""
    captured: dict[str, tuple] = {}

    async def fake_exec(*args, **kwargs):
        captured["args"] = args
        proc = MagicMock()

        async def _communicate():
            return (b"", b"")

        proc.communicate = _communicate
        proc.returncode = 0
        return proc

    params = _load_rule_params("code/imports.yaml", "code.imports.must_resolve")
    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        await _run_via_real_engine(params)

    assert captured["args"][:3] == ("ruff", "check", "src")


async def test_must_resolve_produces_zero_findings_for_genuinely_broken_import(
    tmp_path: Path,
) -> None:
    """Pins #855 findings 1+2: even with an explicit isolated file_path
    (bypassing the verify_context discard above), the real
    ImportResolutionCheck with the rule's live mapping params produces
    zero findings for an import that cannot possibly resolve."""
    bad = tmp_path / "bad.py"
    bad.write_text(
        "import this_module_does_not_exist_anywhere_xyz\n"
        "x = this_module_does_not_exist_anywhere_xyz.foo()\n",
        encoding="utf-8",
    )
    params = _load_rule_params("code/imports.yaml", "code.imports.must_resolve")
    check = ImportResolutionCheck()
    result = await check.verify(bad, params)
    assert result == [], (
        "code.imports.must_resolve's stated law is never actually verified "
        "by the real check -- see #855"
    )


async def test_no_stale_namespace_produces_zero_findings_for_stale_reference(
    tmp_path: Path,
) -> None:
    """Same root cause as above, for the second rule sharing this
    check_type: a textbook stale-namespace import produces zero findings."""
    stale = tmp_path / "stale.py"
    stale.write_text(
        "from features.old_module import legacy_thing\nx = legacy_thing()\n",
        encoding="utf-8",
    )
    params = _load_rule_params("code/imports.yaml", "code.imports.no_stale_namespace")
    check = ImportResolutionCheck()
    result = await check.verify(stale, params)
    assert result == [], (
        "code.imports.no_stale_namespace's stated law is never actually "
        "verified by the real check -- see #855"
    )


async def test_import_resolution_check_silent_passes_when_ruff_absent(
    tmp_path: Path,
) -> None:
    """Pins #855 finding 4: the same G9 tool-absence-is-compliant shape as
    #847, on ImportResolutionCheck rather than QualityGateCheck. This is
    evidence of the defect, not a compliant fixture -- a missing required
    tool must not count as a compliant result for a blocking rule."""
    clean = tmp_path / "clean.py"
    clean.write_text("import os\n\nprint(os.getcwd())\n", encoding="utf-8")
    params = _load_rule_params("code/imports.yaml", "code.imports.must_resolve")
    check = ImportResolutionCheck()
    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=FileNotFoundError(2, "No such file or directory", "ruff"),
    ):
        result = await check.verify(clean, params)
    assert result == []


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
