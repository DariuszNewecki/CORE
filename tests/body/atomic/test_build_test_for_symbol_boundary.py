# tests/body/atomic/test_build_test_for_symbol_boundary.py
"""
Static boundary regression tests for build.test_for_symbol (ADR-140 D10).

These tests verify that the Body write action does not cross the cognitive
boundary — no prompt loading, no cognitive client acquisition, no Will-tier
imports. They are structural, not behavioural: they survive any future
refactor of the cognitive layer and catch regressions at test collection time.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path


# ID: 55dcd8d6-01d8-4b35-9ffa-2b45f6bdbeed
def test_action_does_not_cross_cognitive_boundary() -> None:
    """Body write action must not load prompts, acquire cognitive clients, or import Will."""
    spec = importlib.util.find_spec("body.atomic.build_test_for_symbol_action")
    assert spec is not None, "body.atomic.build_test_for_symbol_action not found"
    source = Path(spec.origin).read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Check ast.Name references (direct name use)
    forbidden_names = {"PromptModel", "aget_client_for_role", "load_generation_budget"}
    names_used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not (forbidden_names & names_used), (
        f"Body write action references cognitive names: {forbidden_names & names_used}"
    )

    # Check attribute access (e.g. core_context.cognitive_service)
    forbidden_attrs = {"cognitive_service", "aget_client_for_role"}
    attrs_used = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert not (forbidden_attrs & attrs_used), (
        f"Body write action accesses cognitive attributes: {forbidden_attrs & attrs_used}"
    )

    # Check imports — no will.* and no shared.infrastructure.llm
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


# ID: fa558561-ba36-4d9e-80a5-ae30dac68b5d
def test_action_requires_generated_code_parameter() -> None:
    """Body write action must declare generated_code as a required (no-default) parameter."""
    import inspect

    from body.atomic.build_test_for_symbol_action import action_build_test_for_symbol

    sig = inspect.signature(action_build_test_for_symbol)
    assert "generated_code" in sig.parameters, (
        "generated_code parameter is missing — "
        "it must be present so FlowExecutor can thread it from the cognitive step"
    )
    param = sig.parameters["generated_code"]
    assert param.default is inspect.Parameter.empty, (
        "generated_code must be required (no default) — "
        "it is produced by the cognitive step, not caller-supplied"
    )


# ID: 013a713a-fa68-4c9c-a5ec-9de74c326b71
def test_action_has_no_generation_mode_parameter() -> None:
    """generation_mode must not appear in the narrowed action signature."""
    import inspect

    from body.atomic.build_test_for_symbol_action import action_build_test_for_symbol

    sig = inspect.signature(action_build_test_for_symbol)
    assert "generation_mode" not in sig.parameters, (
        "generation_mode must be removed from the action — "
        "generation strategy is the cognitive delegate's concern, not the write action's"
    )
