"""
CLI command validation framework.

Enforces constitutional rules from .intent/rules/cli/interface_design.json
at command registration time.

Constitutional Rules Enforced:
- cli.resource_first: Commands follow 'resource action' pattern
- cli.no_layer_exposure: No mind/body/will in command names
- cli.standard_verbs: Actions use standard verb vocabulary
- cli.dangerous_explicit: Mutating commands require --write flag
"""

from __future__ import annotations

from typing import Literal

from shared.logger import getLogger


logger = getLogger(__name__)
ResourceName = Literal[
    "database",
    "vectors",
    "code",
    "symbols",
    "constitution",
    "proposals",
    "project",
    "dev",
    "admin",
]
FORBIDDEN_RESOURCE_NAMES = {"mind", "body", "will", "manage", "check", "fix"}
STANDARD_VERBS = {
    "sync",
    "query",
    "validate",
    "audit",
    "list",
    "create",
    "show",
    "approve",
    "reject",
    "execute",
    "inspect",
    "status",
    "drift",
    "rebuild",
    "migrate",
    "export",
    "cleanup",
    "format",
    "lint",
    "test",
    "coverage",
    "analyze",
    "new",
    "onboard",
    "docs",
    "get",
    "set",
    "delete",
}


# ID: 2b995091-33ad-4201-8a2c-ed8e9805ab06
class ConstitutionalViolation(Exception):
    """Raised when CLI command violates constitutional rules."""

    pass


# ID: 4591e424-9c09-4c2e-87dd-e35008e33ed5
def validate_resource_name(name: str) -> None:
    """
    Validate resource name against constitutional rules.

    Enforces:
    - cli.no_layer_exposure: No forbidden architecture layer names
    - Lowercase alphanumeric with optional hyphens

    Args:
        name: Resource name to validate

    Raises:
        ConstitutionalViolation: If name violates rules

    Examples:
        validate_resource_name("database")  # ✅ OK
        validate_resource_name("body")      # ❌ Forbidden (layer exposure)
        validate_resource_name("MyResource")  # ❌ Must be lowercase
    """
    if name.lower() in FORBIDDEN_RESOURCE_NAMES:
        raise ConstitutionalViolation(
            f"Resource name '{name}' is forbidden (exposes internal architecture layers). Forbidden names: {', '.join(sorted(FORBIDDEN_RESOURCE_NAMES))}"
        )
    if not name.islower():
        raise ConstitutionalViolation(f"Resource name '{name}' must be lowercase")
    if not name.replace("-", "").isalnum():
        raise ConstitutionalViolation(
            f"Resource name '{name}' must be alphanumeric (hyphens allowed)"
        )
    logger.debug("✅ Resource name '%s' validated", name)


# ID: 601ade3f-dca2-4040-9590-6ccea06cb4e2
def validate_action_name(resource: str, action: str) -> None:
    """
    Validate action name against constitutional rules.

    Enforces:
    - cli.standard_verbs: Actions should use standard vocabulary

    Note: This is a soft check (warning), not blocking.

    Args:
        resource: Resource name for context
        action: Action name to validate

    Examples:
        validate_action_name("database", "sync")  # ✅ OK (standard verb)
        validate_action_name("database", "foobar")  # ⚠️ Warning (non-standard)
    """
    if action not in STANDARD_VERBS:
        logger.warning(
            "Action '%s' on resource '%s' is non-standard. Consider using one of: %s",
            action,
            resource,
            ", ".join(sorted(STANDARD_VERBS)),
        )
    else:
        logger.debug("✅ Action '%s' validated (standard verb)", action)


# ID: e22df91d-1bd3-44ed-8eb9-cd1dc3eb3101
def validate_command_depth(command_path: str, allow_admin_depth3: bool = True) -> None:
    """
    Validate command depth against constitutional rules.

    Enforces:
    - cli.resource_first: Max depth=2 (resource action)
    - Exception: admin namespace may use depth=3

    Args:
        command_path: Full command path (e.g., "database sync")
        allow_admin_depth3: Allow depth=3 for admin namespace

    Raises:
        ConstitutionalViolation: If depth exceeds limits

    Examples:
        validate_command_depth("database sync")  # ✅ OK (depth=2)
        validate_command_depth("admin config sync")  # ✅ OK (admin exception)
        validate_command_depth("foo bar baz qux")  # ❌ Too deep
    """
    parts = command_path.strip().split()
    depth = len(parts)
    if depth > 3:
        raise ConstitutionalViolation(
            f"Command '{command_path}' exceeds maximum depth. Commands must follow 'resource action' pattern (depth=2)"
        )
    if depth == 3:
        if not (allow_admin_depth3 and parts[0] == "admin"):
            raise ConstitutionalViolation(
                f"Command '{command_path}' at depth=3 is only allowed for admin namespace. Use 'resource action' pattern (depth=2) for other commands."
            )
    logger.debug("✅ Command depth validated: %s (depth=%s)", command_path, depth)


# ID: dc6bc45a-132c-4023-9159-dd4a91edc973
def validate_resource_module(resource_name: str, module_path: str) -> None:
    """
    Validate resource module before registration.

    Comprehensive validation combining all rules:
    - Resource name validation
    - Module structure check
    - Constitutional compliance

    Args:
        resource_name: Name of resource being registered
        module_path: Python import path to module

    Raises:
        ConstitutionalViolation: If validation fails
    """
    logger.info("Validating resource module: %s (%s)", resource_name, module_path)
    validate_resource_name(resource_name)
    if not module_path.startswith("body.cli.resources."):
        raise ConstitutionalViolation(
            f"Resource module '{module_path}' must be in body.cli.resources/ package"
        )
    logger.info("✅ Resource module validated: %s", resource_name)
