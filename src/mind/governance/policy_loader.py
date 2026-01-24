# src/mind/governance/policy_loader.py

"""
Centralized loaders for constitution-backed policies used by agents and services.
Updated to use consolidated policy files (agent_governance, operations).
"""

from __future__ import annotations

from typing import Any

import yaml

from shared.logger import getLogger
from shared.path_resolver import PathResolver


logger = getLogger(__name__)


def _load_policy_yaml(path_resolver: PathResolver, logical_path: str) -> dict[str, Any]:
    """
    Loads a policy using PathResolver.
    """
    try:
        try:
            path = path_resolver.policy(logical_path)
        except FileNotFoundError:
            path = None

        if not path or not path.exists():
            msg = f"Policy file not found: {logical_path}"
            logger.error(msg)
            # Fallback: try loading relative to intent root if meta lookup failed
            fallback_path = path_resolver.intent_root / logical_path.replace(".", "/")
            if not fallback_path.suffix:
                fallback_path = fallback_path.with_suffix(".yaml")

            if fallback_path.exists():
                logger.info("Found policy at fallback path: %s", fallback_path)
                path = fallback_path
            else:
                raise ValueError(msg)

        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Policy file must be a dictionary: {path}")
        return data
    except Exception as e:
        logger.error("Failed to load policy '{logical_path}': %s", e)
        raise ValueError(f"Failed to load policy '{logical_path}': {e}") from e


# ID: 2c30f0ee-4d7a-4c02-955b-12d080bf0b0c
class PolicyLoader:
    def __init__(self, path_resolver: PathResolver) -> None:
        self._paths = path_resolver

    # ID: 5477bdaa-1466-405a-a8a8-50d15020ebf9
    def load_available_actions(self) -> dict[str, Any]:
        """
        Load available actions from agent_governance.yaml.
        Adapts the new schema to the format expected by PlannerAgent.
        """
        policy = _load_policy_yaml(self._paths, "charter.policies.agent_governance")
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
    def load_micro_proposal_policy(self) -> dict[str, Any]:
        """
        Load Micro-Proposal rules from agent_governance.yaml (autonomy_lanes).
        Adapts to match expected structure.
        """
        policy = _load_policy_yaml(self._paths, "charter.policies.agent_governance")
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


# ID: 604cf7d0-6626-4204-85d2-9943c28835ec
def load_available_actions(path_resolver: PathResolver) -> dict[str, Any]:
    return PolicyLoader(path_resolver).load_available_actions()


# ID: 3a8f9608-e628-48d8-9139-fe297447971e
def load_micro_proposal_policy(path_resolver: PathResolver) -> dict[str, Any]:
    return PolicyLoader(path_resolver).load_micro_proposal_policy()


__all__ = ["PolicyLoader", "load_available_actions", "load_micro_proposal_policy"]
