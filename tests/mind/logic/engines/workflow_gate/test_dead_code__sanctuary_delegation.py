"""Tests for DeadCodeCheck (#585): subprocess invocation delegates to the
shared sanctuary (shared.utils.subprocess_utils.run_vulture).

Pre-#585, DeadCodeCheck.verify called asyncio.create_subprocess_exec inline,
placing subprocess semantics inside the Mind layer (violation of
architecture.layers.no_mind_execution). The refactored shape delegates the
subprocess call to the shared sanctuary; this file verifies the delegation
+ structured-result handling, not subprocess behaviour itself.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mind.logic.engines.workflow_gate.base_check import StructuredViolation
from mind.logic.engines.workflow_gate.checks.dead_code import DeadCodeCheck
from shared.path_resolver import PathResolver
from shared.utils.subprocess_utils import SubprocessResult


def _make_check(repo_root: Path) -> DeadCodeCheck:
    """Construct a DeadCodeCheck pointed at a synthetic repo root."""
    resolver = PathResolver(repo_root=repo_root)
    return DeadCodeCheck(path_resolver=resolver)


# ID: f78bc79a-d3b0-4ce3-9d4c-02ffdc5130cd
async def test_verify_delegates_to_run_vulture(tmp_path: Path) -> None:
    """DeadCodeCheck.verify must route the vulture invocation through
    shared.utils.subprocess_utils.run_vulture — not call subprocess directly.
    """
    check = _make_check(tmp_path)
    fake_result = SubprocessResult(stdout="", stderr="", returncode=0)

    with patch(
        "mind.logic.engines.workflow_gate.checks.dead_code.run_vulture",
        new=AsyncMock(return_value=fake_result),
    ) as mock_vulture:
        await check.verify(file_path=None, params={"confidence": 70})

    mock_vulture.assert_awaited_once()
    call_kwargs = mock_vulture.await_args.kwargs
    assert call_kwargs["target"] == "src/"
    assert call_kwargs["confidence"] == 70
    assert call_kwargs["repo_root"] == tmp_path


# ID: 6f998275-64c5-42a0-8ffa-1f5751e08970
async def test_verify_returns_empty_when_vulture_finds_nothing(
    tmp_path: Path,
) -> None:
    """A clean vulture run (empty stdout) produces no violations."""
    check = _make_check(tmp_path)
    fake_result = SubprocessResult(stdout="", stderr="", returncode=0)

    with patch(
        "mind.logic.engines.workflow_gate.checks.dead_code.run_vulture",
        new=AsyncMock(return_value=fake_result),
    ):
        violations = await check.verify(file_path=None, params={})

    assert violations == []


# ID: b3c9ccf0-5c86-4c01-bd30-2308483e95c2
async def test_verify_emits_one_structured_violation_per_file(tmp_path: Path) -> None:
    """Vulture lines group into one StructuredViolation per file carrying the
    real file_path. A bare string became a "System" finding that the
    audit-violation filter discards, so the rule never reached the blackboard
    (2026-10-04 residue investigation)."""
    check = _make_check(tmp_path)
    fake_stdout = (
        "src/foo.py:12: unused function 'bar' (60% confidence)\n"
        "src/foo.py:30: unused method 'baz' (60% confidence)\n"
        "src/qux.py:3: unused import 'os' (90% confidence)\n"
    )
    fake_result = SubprocessResult(stdout=fake_stdout, stderr="", returncode=0)

    with patch(
        "mind.logic.engines.workflow_gate.checks.dead_code.run_vulture",
        new=AsyncMock(return_value=fake_result),
    ):
        violations = await check.verify(file_path=None, params={})

    assert all(isinstance(v, StructuredViolation) for v in violations)
    by_file = {v.file_path: v for v in violations}
    assert set(by_file) == {"src/foo.py", "src/qux.py"}
    assert by_file["src/foo.py"].context["issue_count"] == 2
    assert by_file["src/foo.py"].context["first_issue_line"] == 12


async def test_verify_filters_report_kinds(tmp_path: Path) -> None:
    """report_kinds keeps only the listed vulture kinds (model fields surface
    as 'unused variable' and are not dead code)."""
    check = _make_check(tmp_path)
    fake_stdout = (
        "src/m.py:5: unused variable 'field_a' (60% confidence)\n"
        "src/m.py:9: unused class 'Gone' (60% confidence)\n"
        "src/n.py:2: unused variable 'field_b' (60% confidence)\n"
    )
    fake_result = SubprocessResult(stdout=fake_stdout, stderr="", returncode=0)

    with patch(
        "mind.logic.engines.workflow_gate.checks.dead_code.run_vulture",
        new=AsyncMock(return_value=fake_result),
    ):
        violations = await check.verify(
            file_path=None, params={"report_kinds": ["class", "function"]}
        )

    assert [(v.file_path, v.context["issue_count"]) for v in violations] == [
        ("src/m.py", 1)
    ]


async def test_verify_ignores_intent_declared_classes(tmp_path: Path) -> None:
    """Classes .intent/ declares for import_module loading (worker
    implementation.class, phase implementation) are passed to vulture as
    ignored names, alongside the mapping's own ignore_names."""
    (tmp_path / ".intent" / "workers").mkdir(parents=True)
    (tmp_path / ".intent" / "workers" / "w.yaml").write_text(
        "implementation:\n  module: will.workers.w\n  class: DeclaredWorker\n"
    )
    (tmp_path / ".intent" / "phases").mkdir(parents=True)
    (tmp_path / ".intent" / "phases" / "p.yaml").write_text(
        "implementation: will.phases.p.DeclaredPhase\n"
    )
    check = _make_check(tmp_path)
    fake_result = SubprocessResult(stdout="", stderr="", returncode=0)

    with patch(
        "mind.logic.engines.workflow_gate.checks.dead_code.run_vulture",
        new=AsyncMock(return_value=fake_result),
    ) as mock_vulture:
        await check.verify(
            file_path=None,
            params={"ignore_names": ["*Engine"], "ignore_decorators": ["@*.command"]},
        )

    kwargs = mock_vulture.await_args.kwargs
    assert set(kwargs["ignore_names"]) == {"*Engine", "DeclaredWorker", "DeclaredPhase"}
    assert kwargs["ignore_decorators"] == ["@*.command"]


# ID: 2ec7648b-0d73-476d-a2ef-a182aa3dc974
async def test_verify_recovers_from_sanctuary_failure(tmp_path: Path) -> None:
    """If run_vulture raises (e.g. binary missing, transient OS error), the
    check returns a single 'Dead code analysis failed: ...' violation rather
    than propagating the exception. Preserves pre-#585 failure semantics so
    the engine sees a structured violation, not an unhandled exception.
    """
    check = _make_check(tmp_path)

    with patch(
        "mind.logic.engines.workflow_gate.checks.dead_code.run_vulture",
        new=AsyncMock(side_effect=FileNotFoundError("vulture not found")),
    ):
        violations = await check.verify(file_path=None, params={})

    assert len(violations) == 1
    assert violations[0].startswith("Dead code analysis failed: ")
    assert "vulture not found" in violations[0]


_TWO_ITEMS = (
    "src/a.py:3: unused function 'old_debt' (60% confidence)\n"
    "src/a.py:9: unused function 'new_dead' (60% confidence)\n"
)


def _write_baseline(tmp_path: Path, entries: list[str]) -> str:
    rel = "enforcement/config/dead_code_baseline.yaml"
    path = tmp_path / ".intent" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("baseline:\n" + "".join(f'  - "{e}"\n' for e in entries))
    return rel


# ID: 5b5c297e-dac9-4717-8c3c-f04d5e1f6786
async def test_baseline_suppresses_recorded_items_only(tmp_path: Path) -> None:
    """Ratchet: an item recorded in the baseline (file::name) is not reported;
    a new one in the same file is. Keyed by name, so line shifts don't matter."""
    rel = _write_baseline(tmp_path, ["src/a.py::old_debt"])
    check = _make_check(tmp_path)

    with patch(
        "mind.logic.engines.workflow_gate.checks.dead_code.run_vulture",
        new=AsyncMock(return_value=SubprocessResult(_TWO_ITEMS, "", 3)),
    ):
        violations = await check.verify(file_path=None, params={"baseline": rel})

    assert len(violations) == 1
    v = violations[0]
    assert isinstance(v, StructuredViolation)
    assert v.context["issue_count"] == 1
    assert "new_dead" in v.context["sample_issues"][0]


# ID: 76c572e8-f152-414d-9004-76e11d9698a0
async def test_fully_baselined_file_reports_nothing(tmp_path: Path) -> None:
    rel = _write_baseline(tmp_path, ["src/a.py::old_debt", "src/a.py::new_dead"])
    check = _make_check(tmp_path)

    with patch(
        "mind.logic.engines.workflow_gate.checks.dead_code.run_vulture",
        new=AsyncMock(return_value=SubprocessResult(_TWO_ITEMS, "", 3)),
    ):
        violations = await check.verify(file_path=None, params={"baseline": rel})

    assert violations == []


# ID: d757ef39-32f4-4609-8940-a8385e34fbd2
async def test_unreadable_baseline_fails_loud(tmp_path: Path) -> None:
    """A declared baseline that cannot be read is a finding, never a silent
    'report everything' or 'report nothing'."""
    check = _make_check(tmp_path)

    with patch(
        "mind.logic.engines.workflow_gate.checks.dead_code.run_vulture",
        new=AsyncMock(return_value=SubprocessResult(_TWO_ITEMS, "", 3)),
    ) as mock_vulture:
        violations = await check.verify(
            file_path=None, params={"baseline": "enforcement/config/missing.yaml"}
        )

    assert len(violations) == 1
    assert violations[0].startswith("Dead code baseline unreadable: ")
    mock_vulture.assert_not_awaited()


# ID: 3a093cc4-7283-433f-944c-05bbfff4bbac
async def test_mapping_check_methods_are_ignored_names(tmp_path: Path) -> None:
    """Methods a mapping dispatches by getattr (params.check_method) are
    declared in .intent/, so vulture is told to ignore them."""
    mappings = tmp_path / ".intent" / "enforcement" / "mappings" / "code"
    mappings.mkdir(parents=True)
    (mappings / "modularity.yaml").write_text(
        "mappings:\n"
        "  modularity.x:\n"
        "    engine: ast_gate\n"
        "    params:\n"
        "      check_method: check_needs_split\n"
    )
    check = _make_check(tmp_path)

    with patch(
        "mind.logic.engines.workflow_gate.checks.dead_code.run_vulture",
        new=AsyncMock(return_value=SubprocessResult("", "", 0)),
    ) as mock_vulture:
        await check.verify(file_path=None, params={})

    assert "check_needs_split" in mock_vulture.await_args.kwargs["ignore_names"]


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
