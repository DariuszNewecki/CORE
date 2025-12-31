# src/mind/governance/check_registry.py
"""
Dynamic check registry for constitutional governance.

Provides lookup and discovery of audit checks without hardcoded imports.
Follows the "Big Boys" pattern - checks are discovered automatically via
introspection rather than explicit registration.

UPDATED: Now discovers shims and bridges defined in the package root to
maintain backward compatibility with constitutional rule migration.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil

import mind.governance.checks as checks
from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger


logger = getLogger(__name__)

# Cache for discovered checks (populated on first access)
_CHECK_REGISTRY: dict[str, type[BaseCheck]] | None = None


# ID: check-discovery-function
# ID: 0666f4e0-cff1-4935-b8d0-80bea980c195
def discover_all_checks() -> dict[str, type[BaseCheck]]:
    """
    Dynamically discovers all BaseCheck subclasses in the checks package.

    Returns a dictionary mapping check class names to check classes.
    This is the SSOT for which checks exist in the system.

    Caches results after first call for performance.
    """
    global _CHECK_REGISTRY

    if _CHECK_REGISTRY is not None:
        return _CHECK_REGISTRY

    check_classes: dict[str, type[BaseCheck]] = {}

    # 1. Discover checks exported in the package root (e.g. shims in __init__.py)
    # This allows us to find LegacyTagCheck, DuplicationCheck, etc. without files.
    for name, obj in inspect.getmembers(checks, inspect.isclass):
        if (
            issubclass(obj, BaseCheck)
            and obj is not BaseCheck
            and not inspect.isabstract(obj)
        ):
            check_classes[name] = obj

    # 2. Discover checks in existing physical submodules
    for _, name, _ in pkgutil.iter_modules(checks.__path__):
        try:
            module = importlib.import_module(f"mind.governance.checks.{name}")

            for item_name, item in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(item, BaseCheck)
                    and item is not BaseCheck
                    and not inspect.isabstract(item)
                ):
                    # Use class name as key
                    # If already present from root (a shim), the submodule wins
                    # (actual physical implementations take precedence)
                    check_classes[item.__name__] = item

                    logger.debug(
                        "Discovered check: %s from %s", item.__name__, module.__name__
                    )

        except Exception as e:
            logger.warning("Failed to import check module %s: %s", name, e)
            continue

    _CHECK_REGISTRY = check_classes
    logger.info(
        "Discovered %d constitutional checks (including legacy shims)",
        len(check_classes),
    )

    return check_classes


# ID: check-lookup-function
# ID: 027002ee-171a-406a-93c6-0cb6d8d37889
def get_check(check_name: str) -> type[BaseCheck]:
    """
    Get a specific check class by name.

    Args:
        check_name: Name of the check class (e.g., "CoverageGovernanceCheck")

    Returns:
        The check class (not instantiated)

    Raises:
        KeyError: If the check doesn't exist
    """
    registry = discover_all_checks()

    if check_name not in registry:
        available = ", ".join(sorted(registry.keys()))
        raise KeyError(f"Check '{check_name}' not found. Available checks: {available}")

    return registry[check_name]


# ID: check-exists-function
# ID: c035b412-f556-4978-bc2a-2ce02707f67d
def check_exists(check_name: str) -> bool:
    """
    Check if a check with the given name exists.

    Args:
        check_name: Name of the check class

    Returns:
        True if the check exists, False otherwise
    """
    registry = discover_all_checks()
    return check_name in registry


# ID: list-all-checks-function
# ID: 94db7c64-3b88-439d-8dae-4fc752d3ca3b
def list_all_checks() -> list[str]:
    """
    List all available check names.

    Returns:
        Sorted list of check class names
    """
    registry = discover_all_checks()
    return sorted(registry.keys())


# ID: clear-cache-function
# ID: 376a93b2-24fe-4dbc-9b16-e3fa443d9d99
def clear_cache() -> None:
    """
    Clear the check registry cache.

    Useful for testing or when checks are added/removed at runtime.
    """
    global _CHECK_REGISTRY
    _CHECK_REGISTRY = None
    logger.debug("Check registry cache cleared")
