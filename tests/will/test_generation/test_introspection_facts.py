"""Tests for will.test_generation.introspection_facts (#589 Tier 1).

The helper produces the ground-truth dict the test-gen prompt is anchored
on; these tests pin its observable contract — shape, async/governance
detection, awaited-call-site grep, graceful failure — so any future
edit gets caught by something other than the eventual LLM hallucinating
again.
"""

from __future__ import annotations

from will.test_generation.introspection_facts import (
    _file_path_to_import_path,
    _find_target_node,
    _has_governance_decorator,
    build_introspection_facts,
)


def test_file_path_to_import_path_strips_src_prefix() -> None:
    assert _file_path_to_import_path("src/body/services/foo.py") == "body.services.foo"


def test_file_path_to_import_path_handles_no_src_prefix() -> None:
    assert _file_path_to_import_path("body/services/foo.py") == "body.services.foo"


def test_file_path_to_import_path_collapses_init() -> None:
    assert (
        _file_path_to_import_path("src/body/services/__init__.py") == "body.services"
    )


def test_has_governance_decorator_matches_atomic_action() -> None:
    assert _has_governance_decorator(
        ["atomic_action(action_id='fix.foo', impact=ActionImpact.WRITE)"]
    )


def test_has_governance_decorator_matches_core_command() -> None:
    assert _has_governance_decorator(["core_command(dangerous=False)"])


def test_has_governance_decorator_rejects_plain_decorators() -> None:
    assert not _has_governance_decorator(["staticmethod", "property", "dataclass"])


def test_facts_for_real_class_includes_awaited_call_sites() -> None:
    """A real class with several ``await self._x.y(...)`` calls surfaces
    the dotted-name list — this is the exact data #572 batch 7 needed
    to avoid the governance_claims_service boundary-mock drift."""
    code = '''
class WidgetService:
    """A widget."""

    def __init__(self, db, vector_size=128):
        self._db = db

    async def fetch(self):
        rows = await self._db.client.read("widgets")
        await self._db.publish(rows)
        return rows
'''
    facts = build_introspection_facts(
        "tests/will/test_generation/test_introspection_facts.py",
        "WidgetService",
        code,
    )
    # AST-side facts work regardless of whether the live import succeeds
    # (this in-test class isn't importable from the file path).
    assert "self._db.client.read" in facts["awaited_call_sites"]
    assert "self._db.publish" in facts["awaited_call_sites"]
    assert facts["decorators"] == []
    assert facts["has_governance_decorator"] is False
    # Live-import side fails for the in-test class — that's fine, it's
    # the documented graceful-failure mode.
    assert facts["introspection_error"] is not None


def test_facts_for_governance_decorated_function_set_governance_flag() -> None:
    """An @atomic_action-decorated function surfaces the decorator in
    full source form and flags has_governance_decorator=True so the
    prompt warns the LLM to use .__wrapped__."""
    code = """
@atomic_action(action_id="fix.demo", impact=ActionImpact.WRITE_CODE)
async def fix_demo(context, write: bool = False):
    return None
"""
    facts = build_introspection_facts(
        "tests/will/test_generation/test_introspection_facts.py",
        "fix_demo",
        code,
    )
    assert facts["has_governance_decorator"] is True
    assert any("atomic_action" in d for d in facts["decorators"])


def test_facts_graceful_failure_on_missing_module() -> None:
    """Pointing at a nonexistent module yields a stable-shape dict with
    introspection_error set — the prompt-side will skip the GROUND
    TRUTH section instead of crashing."""
    facts = build_introspection_facts(
        "src/body/services/nonexistent_module_for_test.py",
        "DefinitelyNotARealClass",
        "",
    )
    assert facts["introspection_error"] is not None
    assert "nonexistent_module_for_test" in facts["introspection_error"]
    # All other keys still present with safe defaults.
    assert facts["public_attrs"] == []
    assert facts["awaited_call_sites"] == []
    assert facts["has_governance_decorator"] is False


def test_facts_signature_is_populated_for_real_importable_class() -> None:
    """The signature field carries the constructor signature for a class
    that's actually importable — the load-bearing data for the DI-drift
    prevention (shape 2 in #589 evidence)."""
    facts = build_introspection_facts(
        "src/shared/path_resolver.py",
        "PathResolver",
        "",  # symbol_code can be empty when we only care about live facts
    )
    assert facts["introspection_error"] is None
    assert facts["kind"] == "class"
    assert "repo_root" in facts["signature"]
    # Public surface includes the documented properties (e.g. repo_root,
    # intent_root, var_dir) — not testing the exact list since
    # PathResolver evolves, but its non-emptiness is load-bearing.
    assert len(facts["public_attrs"]) > 5


def test_find_target_node_returns_none_for_missing_symbol() -> None:
    import ast

    tree = ast.parse("def existing():\n    pass\n")
    assert _find_target_node(tree, "nonexistent") is None


def test_find_target_node_finds_class_def() -> None:
    import ast

    tree = ast.parse("class Foo:\n    pass\n")
    node = _find_target_node(tree, "Foo")
    assert node is not None and node.__class__.__name__ == "ClassDef"
