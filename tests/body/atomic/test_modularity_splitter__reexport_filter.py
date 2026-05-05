"""Regression tests for ModularitySplitter re-export filter (issue #213).

Failure mode (pre-fix): the splitter's two ``__init__.py`` re-export passes
were asymmetric — pass 1 (plan symbols) had no filter, pass 2 (module-level
assigns) only stripped underscore-prefixed names. Conventional private
identifiers (``logger``, ``log``) leaked into the package's public API,
exposing each split module's logger instance as importable from the
package root.

Documented as Failure 5 in ``.specs/papers/CORE-ModularityLessons.md``.
"""

from __future__ import annotations

from pathlib import Path

from body.atomic.modularity_splitter import ModularitySplitter
from body.atomic.split_plan import ModuleSpec, SplitPlan


def _init_content(splitter: ModularitySplitter, src: Path, plan: SplitPlan) -> str:
    result = splitter.split(src, plan)
    init = next(
        (content for path, content in result.files if path.name == "__init__.py"),
        None,
    )
    assert init is not None, (
        f"expected __init__.py in result; got {[p.name for p, _ in result.files]}"
    )
    return init


# ID: 452705a4-15d2-44ab-94c0-0f14b22869e6
def test_logger_not_reexported_when_listed_in_plan_symbols(tmp_path: Path) -> None:
    """If the LLM puts ``logger`` in a module's plan symbols, the splitter
    must not re-export it from __init__.py — would surface the module's
    logger instance as a package-level public attribute.
    """
    src = tmp_path / "monolith.py"
    src.write_text(
        "from __future__ import annotations\n"
        "\n"
        "import logging\n"
        "logger = logging.getLogger(__name__)\n"
        "\n"
        "def alpha():\n"
        "    logger.info('a')\n"
        "    return 1\n"
        "\n"
        "def beta():\n"
        "    return 2\n",
        encoding="utf-8",
    )
    plan = SplitPlan(
        source_file="monolith.py",
        new_package_name="monolith",
        confidence=0.95,
        modules=[
            ModuleSpec(
                module_name="alpha_module",
                symbols=["alpha", "logger"],
                rationale="r",
            ),
            ModuleSpec(module_name="beta_module", symbols=["beta"], rationale="r"),
        ],
    )
    plan.validate()
    init = _init_content(ModularitySplitter(), src, plan)

    for line in init.splitlines():
        if line.startswith("from ."):
            assert "logger" not in line, (
                f"logger leaked into __init__.py re-export line: {line!r}"
            )

    assert "alpha" in init, "public symbol must still be re-exported"
    assert "beta" in init, "other module's public symbol must still be re-exported"


# ID: 78c9c822-819b-448b-8890-30cf6cb52b1d
def test_underscore_and_convention_private_filtered_at_both_passes(
    tmp_path: Path,
) -> None:
    """Both filter sources — plan symbols (pass 1) and module-level
    assignments harvested by reference scan (pass 2) — must reject
    underscore-prefixed AND convention-private names.
    """
    src = tmp_path / "monolith.py"
    src.write_text(
        "from __future__ import annotations\n"
        "\n"
        "import logging\n"
        "logger = logging.getLogger(__name__)\n"
        "log = logger\n"
        "_PRIVATE = 1\n"
        "PUBLIC = 2\n"
        "\n"
        "def public_alpha():\n"
        "    logger.info('a')\n"
        "    log.info('a')\n"
        "    return _PRIVATE + PUBLIC\n"
        "\n"
        "def _private_helper():\n"
        "    return 0\n"
        "\n"
        "def public_beta():\n"
        "    return 1\n",
        encoding="utf-8",
    )
    plan = SplitPlan(
        source_file="monolith.py",
        new_package_name="monolith",
        confidence=0.95,
        modules=[
            ModuleSpec(
                module_name="alpha_module",
                symbols=["public_alpha", "_private_helper", "logger", "log"],
                rationale="r",
            ),
            ModuleSpec(
                module_name="beta_module", symbols=["public_beta"], rationale="r"
            ),
        ],
    )
    plan.validate()
    init = _init_content(ModularitySplitter(), src, plan)

    imported_names: set[str] = set()
    for line in init.splitlines():
        if line.startswith("from .") and " import " in line:
            rhs = line.split(" import ", 1)[1]
            imported_names.update(tok.strip() for tok in rhs.split(","))

    for forbidden in ("logger", "log", "_logger", "_log", "_private_helper", "_PRIVATE"):
        assert forbidden not in imported_names, (
            f"{forbidden!r} leaked into __init__.py re-exports: {imported_names}"
        )

    assert "public_alpha" in imported_names
    assert "public_beta" in imported_names
    assert "PUBLIC" in imported_names, "non-private module-level constant must re-export"


# ID: 26f35d0c-523b-4be0-85f4-04bd41c2e84d
def test_module_with_only_private_symbols_emits_no_import_line(
    tmp_path: Path,
) -> None:
    """If filtering removes every symbol from a module, the splitter must
    skip the entire ``from .{module} import`` line — emitting an empty
    import would be malformed Python.
    """
    src = tmp_path / "monolith.py"
    src.write_text(
        "from __future__ import annotations\n"
        "\n"
        "import logging\n"
        "logger = logging.getLogger(__name__)\n"
        "\n"
        "def _internal():\n"
        "    return 0\n"
        "\n"
        "def public_beta():\n"
        "    return 1\n",
        encoding="utf-8",
    )
    plan = SplitPlan(
        source_file="monolith.py",
        new_package_name="monolith",
        confidence=0.95,
        modules=[
            ModuleSpec(
                module_name="alpha_module",
                symbols=["_internal", "logger"],
                rationale="r",
            ),
            ModuleSpec(
                module_name="beta_module", symbols=["public_beta"], rationale="r"
            ),
        ],
    )
    plan.validate()
    init = _init_content(ModularitySplitter(), src, plan)

    for line in init.splitlines():
        if line.startswith("from .alpha_module"):
            raise AssertionError(
                f"alpha_module had no public symbols after filter; "
                f"the splitter must not emit any 'from .alpha_module import' line, "
                f"got: {line!r}"
            )

    assert "from .beta_module import public_beta" in init
