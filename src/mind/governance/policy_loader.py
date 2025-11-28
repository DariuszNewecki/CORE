# src/mind/governance/policy_loader.py

"""
Centralized loaders for constitution-backed policies used by agents and services.
Updated to use consolidated policy files (agent_governance, operations).
"""

from __future__ import annotations

from typing import Any

import yaml
from shared.config import settings
from shared.logger import getLogger

logger = getLogger(__name__)


def _load_policy_yaml(logical_path: str) -> dict[str, Any]:
    """
    Loads a policy using the settings pathfinder (meta.yaml aware).
    """
    try:
        path = settings.get_path(logical_path)
        if not path.exists():
            msg = f"Policy file not found: {path}"
            logger.error(msg)
            # Fallback: try loading relative to repo root if meta lookup failed
            # or if the file is standard but not in meta yet during bootstrapping
            fallback_path = (
                settings.REPO_PATH / ".intent" / logical_path.replace(".", "/")
            )
            if not fallback_path.suffix:
                fallback_path = fallback_path.with_suffix(".yaml")

            if fallback_path.exists():
                logger.info(f"Found policy at fallback path: {fallback_path}")
                path = fallback_path
            else:
                raise ValueError(msg)

        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Policy file must be a dictionary: {path}")
        return data
    except Exception as e:
        logger.error(f"Failed to load policy '{logical_path}': {e}")
        raise ValueError(f"Failed to load policy '{logical_path}': {e}") from e


# ID: 5477bdaa-1466-405a-a8a8-50d15020ebf9
def load_available_actions() -> dict[str, Any]:
    """
    Load available actions from agent_governance.yaml.
    Adapts the new schema to the format expected by PlannerAgent.
    """
    policy = _load_policy_yaml("charter.policies.agent_governance")
    # New location: planner_actions
    actions = policy.get("planner_actions")

    if not actions:
        # Fallback for backward compatibility
        actions = policy.get("actions", [])

    if not actions:
        logger.warning(
            "'planner_actions' section missing in agent_governance.yaml, returning empty list"
        )
        return {"actions": []}

    # Wrap in dict to match expected return signature
    return {"actions": actions}


# ID: d921aae8-c492-4e39-9aba-d5d2ad89af09
def load_micro_proposal_policy() -> dict[str, Any]:
    """
    Load Micro-Proposal rules from agent_governance.yaml (autonomy_lanes).
    Adapts to match expected structure.
    """
    policy = _load_policy_yaml("charter.policies.agent_governance")
    lanes = policy.get("autonomy_lanes", {}).get("micro_proposals", {})

    if not lanes:
        logger.warning(
            "'autonomy_lanes.micro_proposals' missing in agent_governance.yaml"
        )
        return {"rules": []}

    # Construct the rule object expected by MicroProposalExecutor
    # We combine safe_paths/forbidden_paths into one rule
    path_rule = {
        "id": "safe_paths",
        "allowed_paths": lanes.get("safe_paths", []),
        "forbidden_paths": lanes.get("forbidden_paths", []),
    }

    # We verify actions against allowed_actions
    action_rule = {
        "id": "safe_actions",
        "allowed_actions": lanes.get("allowed_actions", []),
    }

    # Return in format expected by MicroProposalValidator
    return {"policy_id": policy.get("policy_id"), "rules": [path_rule, action_rule]}


__all__ = ["load_available_actions", "load_micro_proposal_policy"]
