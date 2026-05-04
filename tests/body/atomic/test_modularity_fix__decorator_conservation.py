"""Regression tests for the decorator conservation gate in
``action_fix_modularity`` (issue #211).

The gate runs after ``ModularitySplitter`` produces files but before the
LLM-backed Logic Conservation Gate. If a registration decorator
(``@register_action``, ``@atomic_action``) was on a function or class in
the original source but is absent from every produced file, the action
must abort with ``error="decorator_loss_detected"`` and the list of
missing decorators — fail fast, save the LLM call.
"""

from __future__ import annotations

from body.atomic.modularity_fix import _check_decorator_conservation


def test_gate_passes_when_decorators_preserved() -> None:
    original = (
        "@register_action(action_id='x')\n"
        "def alpha():\n"
        "    return 1\n"
        "\n"
        "def beta():\n"
        "    return 2\n"
    )
    files = [
        {
            "path": "x/alpha.py",
            "content": "@register_action(action_id='x')\ndef alpha():\n    return 1\n",
        },
        {"path": "x/beta.py", "content": "def beta():\n    return 2\n"},
        {
            "path": "x/__init__.py",
            "content": "from .alpha import alpha\nfrom .beta import beta\n",
        },
    ]
    assert _check_decorator_conservation(original, files) == []


def test_gate_detects_register_action_loss() -> None:
    original = (
        "@register_action(action_id='sync.db', description='d')\n"
        "async def action_sync_db():\n"
        "    return None\n"
        "\n"
        "def helper():\n"
        "    return 0\n"
    )
    files = [
        {
            "path": "x/sync_db.py",
            "content": "async def action_sync_db():\n    return None\n",
        },
        {"path": "x/helper.py", "content": "def helper():\n    return 0\n"},
        {
            "path": "x/__init__.py",
            "content": (
                "from .sync_db import action_sync_db\nfrom .helper import helper\n"
            ),
        },
    ]
    missing = _check_decorator_conservation(original, files)
    assert missing == ["@register_action on action_sync_db"]


def test_gate_detects_stacked_decorator_loss() -> None:
    """Both ``@register_action`` and ``@atomic_action`` are recorded; if the
    splitter strips them all, both must show up in the missing list."""
    original = (
        "@register_action(action_id='sync.db')\n"
        "@atomic_action(action_id='sync.db')\n"
        "async def action_sync_db():\n"
        "    return None\n"
        "\n"
        "def helper():\n"
        "    return 0\n"
    )
    files = [
        {
            "path": "x/sync_db.py",
            "content": "async def action_sync_db():\n    return None\n",
        },
        {"path": "x/helper.py", "content": "def helper():\n    return 0\n"},
    ]
    missing = _check_decorator_conservation(original, files)
    assert "@register_action on action_sync_db" in missing
    assert "@atomic_action on action_sync_db" in missing


def test_gate_skips_init_file() -> None:
    """``__init__.py`` carries re-exports, not definitions, so it must not
    be treated as a place where decorators could legitimately live."""
    original = "@atomic_action(action_id='x')\nasync def alpha():\n    return None\n"
    files = [
        {"path": "x/__init__.py", "content": "from .alpha import alpha\n"},
        {
            "path": "x/alpha.py",
            "content": "@atomic_action(action_id='x')\nasync def alpha():\n    return None\n",
        },
    ]
    assert _check_decorator_conservation(original, files) == []


def test_gate_no_op_for_unrelated_decorators() -> None:
    """``@dataclass``, ``@staticmethod`` etc. are not preserve-targets;
    losing them is the splitter's problem, not the conservation gate's."""
    original = "@dataclass\nclass Alpha:\n    x: int = 0\n"
    files = [{"path": "x/alpha.py", "content": "class Alpha:\n    x: int = 0\n"}]
    assert _check_decorator_conservation(original, files) == []


def test_gate_handles_attribute_decorator_form() -> None:
    """``@registry.register_action`` form must still be matched on the
    trailing identifier."""
    original = (
        "import registry\n"
        "\n"
        "@registry.register_action(action_id='x')\n"
        "def alpha():\n"
        "    return 1\n"
    )
    files = [
        {"path": "x/alpha.py", "content": "def alpha():\n    return 1\n"},
    ]
    missing = _check_decorator_conservation(original, files)
    assert missing == ["@register_action on alpha"]
