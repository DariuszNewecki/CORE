# tests/body/atomic/test_modularity_fix_boundary.py
"""
Static boundary regression tests for fix.modularity (ADR-140 D10, #769).

These tests verify that the Body write action does not cross the cognitive
boundary — no prompt loading, no cognitive client acquisition, no Will-tier
imports. They are structural, not behavioural: they survive any future
refactor of the cognitive layer and catch regressions at test collection time.
Sibling to test_build_test_for_symbol_boundary.py.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path


# ID: c7e5a3b1-4d2f-4a6c-8e9d-1f2a3b4c5d6e
def test_action_does_not_cross_cognitive_boundary() -> None:
    """Body write action must not load prompts, acquire cognitive clients, or import Will."""
    spec = importlib.util.find_spec("body.atomic.modularity_fix")
    assert spec is not None, "body.atomic.modularity_fix not found"
    source = Path(spec.origin).read_text(encoding="utf-8")
    tree = ast.parse(source)

    forbidden_names = {"PromptModel", "aget_client_for_role"}
    names_used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not (forbidden_names & names_used), (
        f"Body write action references cognitive names: {forbidden_names & names_used}"
    )

    forbidden_attrs = {"cognitive_service", "aget_client_for_role"}
    attrs_used = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert not (forbidden_attrs & attrs_used), (
        f"Body write action accesses cognitive attributes: {forbidden_attrs & attrs_used}"
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not module.startswith("will."), (
                f"Body write action imports from will layer: {module}"
            )
            assert "shared.infrastructure.llm" not in module, (
                f"Body write action imports LLM infrastructure: {module}"
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("will."), (
                    f"Body write action imports from will layer: {alias.name}"
                )


# ID: d8f6b4c2-5e3a-4b7d-9f0e-2a3b4c5d6e7f
def test_action_requires_resolved_file_path_and_plan_raw() -> None:
    """Body write action must declare resolved_file_path and plan_raw as
    required (no-default) parameters."""
    import inspect

    from body.atomic.modularity_fix import action_fix_modularity

    sig = inspect.signature(action_fix_modularity)
    for name in ("resolved_file_path", "plan_raw"):
        assert name in sig.parameters, (
            f"{name} parameter is missing — it must be present so "
            "FlowExecutor can thread it from the analyze.modularity_seam "
            "cognitive step"
        )
        param = sig.parameters[name]
        assert param.default is inspect.Parameter.empty, (
            f"{name} must be required (no default) — it is produced by "
            "the cognitive step, not caller-supplied"
        )


# ID: e9a7c5d3-6f4b-4c8e-a0f1-3b4c5d6e7f8a
def test_action_has_no_file_path_parameter() -> None:
    """file_path (the pre-migration optional target-selection param) must
    not appear in the narrowed action signature — target resolution is the
    cognitive delegate's concern, not the write action's."""
    import inspect

    from body.atomic.modularity_fix import action_fix_modularity

    sig = inspect.signature(action_fix_modularity)
    assert "file_path" not in sig.parameters, (
        "file_path must be removed from the action — resolved_file_path "
        "(produced by the cognitive step) replaces it"
    )
