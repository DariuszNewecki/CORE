"""Regression tests for ModularitySplitter decorator preservation (issue #211).

Failure mode (pre-fix): ``_extract_node_source`` started extraction at
``node.lineno - 1``, which points at the ``def``/``class`` line and silently
dropped any decorators. Splits of files containing ``@register_action`` or
``@atomic_action`` produced operationally broken output that nonetheless
passed the line-based Logic Conservation Gate.
"""

from __future__ import annotations

from pathlib import Path

from body.atomic.modularity_splitter import ModularitySplitter
from body.atomic.split_plan import ModuleSpec, SplitPlan


def _split_get(
    splitter: ModularitySplitter, src: Path, plan: SplitPlan, mod_name: str
) -> str:
    result = splitter.split(src, plan)
    target = next(
        (content for path, content in result.files if path.name == f"{mod_name}.py"),
        None,
    )
    assert target is not None, (
        f"expected {mod_name}.py in result; got {[p.name for p, _ in result.files]}"
    )
    return target


def _two_module_plan(symbols_a: list[str], symbols_b: list[str]) -> SplitPlan:
    plan = SplitPlan(
        source_file="monolith.py",
        new_package_name="monolith",
        confidence=0.95,
        modules=[
            ModuleSpec(module_name="alpha_module", symbols=symbols_a, rationale="r"),
            ModuleSpec(module_name="beta_module", symbols=symbols_b, rationale="r"),
        ],
    )
    plan.validate()
    return plan


def test_single_decorator_preserved(tmp_path: Path) -> None:
    src = tmp_path / "monolith.py"
    src.write_text(
        "from __future__ import annotations\n"
        "\n"
        "def deco(f):\n"
        "    return f\n"
        "\n"
        "@deco\n"
        "def alpha():\n"
        "    return 1\n"
        "\n"
        "def beta():\n"
        "    return 2\n",
        encoding="utf-8",
    )
    plan = _two_module_plan(["deco", "alpha"], ["beta"])
    content = _split_get(ModularitySplitter(), src, plan, "alpha_module")
    assert "@deco" in content
    assert "def alpha" in content
    # Decorator must precede the def line.
    assert content.index("@deco") < content.index("def alpha")


def test_stacked_decorators_preserved(tmp_path: Path) -> None:
    src = tmp_path / "monolith.py"
    src.write_text(
        "from __future__ import annotations\n"
        "\n"
        "def deco_a(f):\n"
        "    return f\n"
        "\n"
        "def deco_b(f):\n"
        "    return f\n"
        "\n"
        "@deco_a\n"
        "@deco_b\n"
        "def alpha():\n"
        "    return 1\n"
        "\n"
        "def beta():\n"
        "    return 2\n",
        encoding="utf-8",
    )
    plan = _two_module_plan(["deco_a", "deco_b", "alpha"], ["beta"])
    content = _split_get(ModularitySplitter(), src, plan, "alpha_module")
    assert "@deco_a" in content
    assert "@deco_b" in content
    a = content.index("@deco_a")
    b = content.index("@deco_b")
    d = content.index("def alpha")
    assert a < b < d, "stacked decorators must appear in original order above def"


def test_class_decorator_preserved(tmp_path: Path) -> None:
    src = tmp_path / "monolith.py"
    src.write_text(
        "from __future__ import annotations\n"
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass\n"
        "class Alpha:\n"
        "    x: int = 0\n"
        "\n"
        "class Beta:\n"
        "    pass\n",
        encoding="utf-8",
    )
    plan = _two_module_plan(["Alpha"], ["Beta"])
    content = _split_get(ModularitySplitter(), src, plan, "alpha_module")
    assert "@dataclass" in content
    assert "class Alpha" in content
    assert content.index("@dataclass") < content.index("class Alpha")


def test_id_anchor_preserved_when_decorators_present(tmp_path: Path) -> None:
    """The ``# ID:`` constitutional anchor must survive even when decorators
    sit between it and the ``def`` line."""
    src = tmp_path / "monolith.py"
    src.write_text(
        "from __future__ import annotations\n"
        "\n"
        "def deco(f):\n"
        "    return f\n"
        "\n"
        "# ID: aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee\n"
        "@deco\n"
        "def alpha():\n"
        "    return 1\n"
        "\n"
        "def beta():\n"
        "    return 2\n",
        encoding="utf-8",
    )
    plan = _two_module_plan(["deco", "alpha"], ["beta"])
    content = _split_get(ModularitySplitter(), src, plan, "alpha_module")
    assert "# ID: aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" in content
    assert "@deco" in content
    assert "def alpha" in content
    id_idx = content.index("# ID:")
    deco_idx = content.index("@deco")
    def_idx = content.index("def alpha")
    assert id_idx < deco_idx < def_idx, "ID anchor must sit above the decorator block"


def test_register_action_decorator_call_form_preserved(tmp_path: Path) -> None:
    """The realistic ``@register_action(action_id=...)`` call-form must
    survive intact — this is the exact pattern that broke in sync_actions."""
    src = tmp_path / "monolith.py"
    src.write_text(
        "from __future__ import annotations\n"
        "\n"
        "def register_action(**_):\n"
        "    def wrap(f):\n"
        "        return f\n"
        "    return wrap\n"
        "\n"
        "def atomic_action(**_):\n"
        "    def wrap(f):\n"
        "        return f\n"
        "    return wrap\n"
        "\n"
        "@register_action(action_id='sync.db', description='d')\n"
        "@atomic_action(action_id='sync.db', intent='i')\n"
        "async def action_sync_db():\n"
        "    return None\n"
        "\n"
        "def helper():\n"
        "    return 0\n",
        encoding="utf-8",
    )
    plan = _two_module_plan(
        ["register_action", "atomic_action", "action_sync_db"], ["helper"]
    )
    content = _split_get(ModularitySplitter(), src, plan, "alpha_module")
    assert "@register_action(action_id='sync.db'" in content
    assert "@atomic_action(action_id='sync.db'" in content
    assert "async def action_sync_db" in content
