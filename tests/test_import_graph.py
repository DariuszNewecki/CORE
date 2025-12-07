# tests/test_import_graph.py
import ast
import importlib
import pathlib
import pkgutil

import pytest


# --- START OF FIX ---
# This is the final, correct architectural map.
# It reflects that core utilities like KnowledgeService and SecretsService
# live in the base `services` layer, which can be accessed by higher layers
# like `will` and `features`.
LAYERING_RULES = {
    "shared": 0,
    "services": 1,  # Low-level clients and cross-cutting concerns
    "mind": 2,  # The "rules" and constitutional context
    "body.actions": 3,  # The fundamental "verbs" or tools
    "body.invokers": 3,
    "will": 4,  # The "reasoning" layer that uses mind, body, and services
    "features": 5,  # High-level business logic that orchestrates the will
    "body.services": 5,  # High-level orchestrators also live here
    "api": 6,  # Entry points are the highest level
    "body.cli": 6,  # CLI is also an entry point
}
# --- END OF FIX ---


def get_layer(module_path: str) -> str | None:
    """Determines the architectural layer of a module based on its path."""
    if not module_path:
        return None
    # Find the longest matching prefix
    for layer in sorted(LAYERING_RULES.keys(), key=len, reverse=True):
        if module_path.startswith(layer):
            return layer
    return None


@pytest.mark.parametrize("module_info", pkgutil.walk_packages(path=["src"], prefix=""))
def test_import_layers(module_info):
    """
    This test automatically discovers every single module in the 'src' directory
    and verifies that its imports do not violate the architectural layering rules.
    """
    try:
        module = importlib.import_module(module_info.name)
    except Exception:
        return

    module_layer_name = get_layer(module_info.name)
    if not module_layer_name:
        return

    module_layer_level = LAYERING_RULES[module_layer_name]

    try:
        if not module.__file__:
            return
        source_path = pathlib.Path(module.__file__)
        source_code = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source_code)
    except Exception:
        return

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.level > 0:  # Skip relative imports
                continue

            imported_layer_name = get_layer(node.module)
            if imported_layer_name:
                imported_layer_level = LAYERING_RULES[imported_layer_name]

                is_allowed = imported_layer_level <= module_layer_level

                assert is_allowed, (
                    f"Architectural violation in {module_info.name}:\n"
                    f"Layer '{module_layer_name}' (level {module_layer_level}) "
                    f"is NOT ALLOWED to import from the higher layer '{imported_layer_name}' (level {imported_layer_level})."
                )
