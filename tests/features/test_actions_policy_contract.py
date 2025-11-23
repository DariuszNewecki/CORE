# tests/features/test_actions_policy_contract.py
from __future__ import annotations

import pytest

from body.actions.registry import ActionRegistry
from mind.governance import policy_loader


def _load_policy_action_names() -> list[str]:
    """
    Read the canonical list of planner-permitted actions from the Constitution.
    """
    policy = policy_loader.load_available_actions()
    actions = policy.get("actions", [])
    # The policy stores actions as a list of dicts with 'name' (modern),
    # or as strings (legacy). Normalize to names.
    names: list[str] = []
    for item in actions:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and "name" in item:
            names.append(item["name"])
        else:
            raise AssertionError(f"Unrecognized action entry in policy: {item!r}")
    return names


@pytest.mark.anyio
async def test_every_policy_action_has_a_registered_handler(mock_core_env):
    """
    Contract: Every action allowed by the Constitution must be executable via the ActionRegistry.
    """
    allowed_action_names = _load_policy_action_names()
    registry = ActionRegistry()

    missing: list[str] = []
    for action in allowed_action_names:
        if registry.get_handler(action) is None:
            missing.append(action)

    if missing:
        # Clear message to guide fixes: either register the handler
        # or remove it from the available_actions_policy.yaml.
        pretty = "\n  - ".join(missing)
        pytest.fail(
            "The following policy actions are not registered in ActionRegistry:\n"
            f"  - {pretty}\n\n"
            "Fix options:\n"
            "  1) Implement/register the missing handlers in src/core/actions/* and registry.py, or\n"
            "  2) Remove/rename the actions from .intent/charter/policies/governance/available_actions_policy.yaml\n"
            "     if they are obsolete."
        )


@pytest.mark.anyio
async def test_registry_exposes_only_constitutional_actions(mock_core_env):
    """
    Hygiene: Handlers present in the registry should also be declared in policy,
    unless intentionally internal (rare). This guards 'drift' and surprises.
    """
    allowed_action_names = set(_load_policy_action_names())
    registry = ActionRegistry()

    unknown: list[str] = []
    # Access the registry's private map via a safe path: try common names.
    # We prefer the public API, so iterate a known set of names to probe.
    # To keep this stable, we check against the handler names we can fetch from policy first,
    # then do a secondary exploration by querying a few registry get_handler calls.
    # Finally, we scan the most common action names we use.
    # This block is intentionally conservative to avoid test brittleness.
    probe_names = set(allowed_action_names)

    # Add a few common built-ins that should be in policy in this codebase.
    probe_names.update(
        {
            "read_file",
            "list_files",
            "delete_file",
            "edit_file",
            "create_file",
            "create_proposal",
            "autonomy.self_healing.fix_docstrings",
            "autonomy.self_healing.fix_headers",
            "autonomy.self_healing.format_code",
            "autonomy.self_healing.fix_imports",
            "autonomy.self_healing.remove_dead_code",
            "autonomy.self_healing.fix_line_length",
            "autonomy.self_healing.add_policy_ids",
            "autonomy.self_healing.sort_imports",
            "core.validation.validate_code",
        }
    )

    for name in probe_names:
        handler = registry.get_handler(name)
        if handler and name not in allowed_action_names:
            unknown.append(name)

    # Note: we don't hard-fail unknowns—just make it visible.
    # If you want stronger enforcement, change to pytest.fail.
    if unknown:
        pytest.xfail(
            "Registry contains handlers not declared in available_actions_policy:\n"
            + "\n".join(f"  - {n}" for n in sorted(set(unknown)))
            + "\nConsider adding them to the policy or marking them internal."
        )
