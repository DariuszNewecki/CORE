# tests/will/phases/test_investigation_phase.py

"""runtime.investigate executes read-only and reaches no mutation surface (#895 U2)."""

from __future__ import annotations

import ast
import inspect as inspect_module
from pathlib import Path
from typing import Any

import pytest

import will.phases.investigation_phase as investigation_module
from will.agents.investigation_planner import InvestigationStep
from will.phases.investigation_phase import InvestigationPhase


class _StubGitService:
    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path


class _StubCoreContext:
    def __init__(self, repo_path: Path) -> None:
        self.git_service = _StubGitService(repo_path)


class _StubWorkflowContext:
    def __init__(self, parse_data: dict[str, Any]) -> None:
        self.goal = "evaluate the target"
        self.workflow_type = "evaluation"
        self.write = False
        self.results: dict[str, Any] = {"parse": parse_data}


def _parse_data(steps: list[InvestigationStep]) -> dict[str, Any]:
    return {
        "investigation_plan": steps,
        "reconnaissance": {
            "available": True,
            "raw": {
                "file_count": 3,
                "layout": {".": 1, "src": 2},
                "artifact_types_present": {"python": 2},
                "unclassified_count": 1,
                "unclassified_suffixes": {".txt": 1},
            },
        },
    }


@pytest.fixture()
def target(tmp_path: Path) -> Path:
    (tmp_path / "README.md").write_text("# hello\nworld\n", encoding="utf-8")
    return tmp_path


@pytest.mark.asyncio
async def test_layout_step_produces_a_grounded_finding(target: Path) -> None:
    phase = InvestigationPhase(_StubCoreContext(target))  # type: ignore[arg-type]
    ctx = _StubWorkflowContext(
        _parse_data([InvestigationStep("shape", "inspect.layout", {})])
    )

    result = await phase.execute(ctx)  # type: ignore[arg-type]

    assert result.ok is True
    finding = result.data["findings"][0]
    assert finding["category"] == "layout"
    assert "3 files" in finding["statement"]
    assert finding["evidence_refs"]


@pytest.mark.asyncio
async def test_inspect_path_reads_within_the_target(target: Path) -> None:
    phase = InvestigationPhase(_StubCoreContext(target))  # type: ignore[arg-type]
    ctx = _StubWorkflowContext(
        _parse_data(
            [InvestigationStep("read it", "inspect.path", {"path": "README.md"})]
        )
    )

    result = await phase.execute(ctx)  # type: ignore[arg-type]

    finding = result.data["findings"][0]
    assert finding["path"] == "README.md"
    assert "File exists" in finding["statement"]


@pytest.mark.asyncio
async def test_path_escaping_the_target_is_refused_not_read(target: Path) -> None:
    phase = InvestigationPhase(_StubCoreContext(target))  # type: ignore[arg-type]
    ctx = _StubWorkflowContext(
        _parse_data(
            [InvestigationStep("escape", "inspect.path", {"path": "../../etc/passwd"})]
        )
    )

    result = await phase.execute(ctx)  # type: ignore[arg-type]

    assert "outside the bound target" in result.data["findings"][0]["statement"]


@pytest.mark.asyncio
async def test_a_missing_plan_is_explicit_unavailable(target: Path) -> None:
    """An apparatus failure, distinct from an investigation that found nothing."""
    phase = InvestigationPhase(_StubCoreContext(target))  # type: ignore[arg-type]
    ctx = _StubWorkflowContext({})

    result = await phase.execute(ctx)  # type: ignore[arg-type]

    assert result.ok is False
    assert result.error.startswith("UNAVAILABLE:")


@pytest.mark.asyncio
async def test_an_unhandled_step_fails_rather_than_improvising(target: Path) -> None:
    phase = InvestigationPhase(_StubCoreContext(target))  # type: ignore[arg-type]
    ctx = _StubWorkflowContext(
        _parse_data([InvestigationStep("odd", "inspect.unknown", {})])
    )

    result = await phase.execute(ctx)  # type: ignore[arg-type]

    assert result.ok is False
    assert result.data["unsupported_steps"] == ["inspect.unknown"]


def test_module_reaches_no_mutation_surface() -> None:
    """The boundary is a property of what this module references, not of its prose.

    Checked over the AST rather than the source text: the module docstring names
    ActionExecutor and Proposal precisely to say it does not use them, and a
    substring check cannot tell an explanation from a call. Imported names,
    attribute accesses and bare identifiers are all inspected, so adding the
    import fails here rather than in review.
    """
    forbidden = {
        "ActionExecutor",
        "Proposal",
        "FileHandler",
        "action_registry",
        "write_text",
        "write_bytes",
        "unlink",
        "mkdir",
    }

    tree = ast.parse(inspect_module.getsource(investigation_module))
    referenced: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                referenced.update(alias.name.split("."))
        elif isinstance(node, ast.ImportFrom):
            referenced.update((node.module or "").split("."))
            referenced.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Attribute):
            referenced.add(node.attr)
        elif isinstance(node, ast.Name):
            referenced.add(node.id)

    leaked = forbidden & referenced
    assert not leaked, f"investigation phase must not reference {sorted(leaked)}"


def test_the_boundary_test_would_catch_a_real_violation() -> None:
    """Guard the guard: the AST check must actually fire on a mutating import."""
    tree = ast.parse("from body.infrastructure.storage.file_handler import FileHandler")
    referenced = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    assert "FileHandler" in referenced
