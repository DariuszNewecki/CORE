# src/cli/logic/autonomy/actions.py

"""Refactored logic for src/body/cli/logic/autonomy/actions.py."""

from __future__ import annotations


# ID: 2b856f28-158c-45e4-95f1-ad85db4bb203
def parse_action_options(action_strs: list[str]) -> list[dict]:
    """Parse CLI action strings (action_id:key=val) into plain dicts.

    Returns dicts with keys {action_id, parameters, order} matching the
    POST /v1/proposals action body schema. Preserves input order.
    """
    proposal_actions: list[dict] = []
    for i, action_str in enumerate(action_strs):
        if ":" in action_str:
            action_id, params_str = action_str.split(":", 1)
            parameters: dict[str, str] = {}
            for param in params_str.split(","):
                if "=" in param:
                    key, value = param.split("=", 1)
                    parameters[key.strip()] = value.strip()
        else:
            action_id = action_str
            parameters = {}

        proposal_actions.append(
            {"action_id": action_id, "parameters": parameters, "order": i}
        )
    return proposal_actions


# ID: de1a1d12-a10b-49a8-a121-f58003db7f26
def get_action_help_text() -> str:
    return "Available actions: fix.format, fix.ids, fix.headers, fix.docstrings, fix.logging"
