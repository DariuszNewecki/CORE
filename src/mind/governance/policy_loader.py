# src/mind/governance/policy_loader.py

"""
Centralized loaders for constitution-backed policies used by agents and services.

CONSTITUTIONAL COMPLIANCE:
- Uses PathResolver for all .intent/ path resolution
- No hardcoded directory paths
- Policies loaded from current .intent/ structure (phases/, workflows/, rules/)
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

    Args:
        path_resolver: PathResolver instance for path resolution
        logical_path: Logical path to policy (e.g., "phases.planning" or "workflows.full_feature_development")

    Returns:
        Loaded policy document as dict

    Raises:
        ValueError: If policy file not found or invalid
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
        logger.error("Failed to load policy '%s': %s", logical_path, e)
        raise ValueError(f"Failed to load policy '{logical_path}': {e}") from e


# ID: 2c30f0ee-4d7a-4c02-955b-12d080bf0b0c
class PolicyLoader:
    """
    Loads policy documents from .intent/ structure using PathResolver.

    CONSTITUTIONAL COMPLIANCE:
    - All paths resolved through PathResolver
    - No direct filesystem access
    - Supports new .intent/ structure (no charter/ subdirectory)
    """

    def __init__(self, path_resolver: PathResolver) -> None:
        self._paths = path_resolver

    # ID: 5477bdaa-1466-405a-a8a8-50d15020ebf9
    def load_available_actions(self) -> dict[str, Any]:
        """
        Load available actions from agent_governance policy.

        Searches for agent_governance in:
        - .intent/phases/
        - .intent/workflows/
        - .intent/rules/ (as fallback)

        Returns:
            Dict with 'actions' key containing list of available actions
        """
        # FIXED: Removed 'charter.policies.' prefix - no longer exists in new structure
        # Try multiple possible locations for agent_governance
        policy_paths = [
            "phases.agent_governance",
            "workflows.agent_governance",
            "rules.will.agent_governance",
        ]

        policy = None
        for path in policy_paths:
            try:
                policy = _load_policy_yaml(self._paths, path)
                logger.debug("Loaded agent_governance from: %s", path)
                break
            except (ValueError, FileNotFoundError):
                continue

        if not policy:
            logger.warning(
                "agent_governance policy not found in any expected location, returning empty actions"
            )
            return {"actions": []}

        # New location: planner_actions
        actions = policy.get("planner_actions")

        if not actions:
            # Fallback for backward compatibility
            actions = policy.get("actions", [])

        if not actions:
            logger.warning(
                "'planner_actions' section missing in agent_governance, returning empty list"
            )
            return {"actions": []}

        # Wrap in dict to match expected return signature
        return {"actions": actions}

    # ID: d921aae8-c492-4e39-9aba-d5d2ad89af09
    def load_micro_proposal_policy(self) -> dict[str, Any]:
        """
        Load Micro-Proposal rules from agent_governance (autonomy_lanes section).

        Returns:
            Dict containing policy_id and rules for micro-proposal validation
        """
        # FIXED: Removed 'charter.policies.' prefix - no longer exists in new structure
        # Try multiple possible locations for agent_governance
        policy_paths = [
            "phases.agent_governance",
            "workflows.agent_governance",
            "rules.will.agent_governance",
        ]

        policy = None
        for path in policy_paths:
            try:
                policy = _load_policy_yaml(self._paths, path)
                logger.debug("Loaded agent_governance from: %s", path)
                break
            except (ValueError, FileNotFoundError):
                continue

        if not policy:
            logger.warning("agent_governance policy not found, returning empty rules")
            return {"rules": []}

        lanes = policy.get("autonomy_lanes", {}).get("micro_proposals", {})

        if not lanes:
            logger.warning(
                "'autonomy_lanes.micro_proposals' missing in agent_governance"
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
    """
    Load available actions using PathResolver.

    Args:
        path_resolver: PathResolver instance for .intent/ access

    Returns:
        Dict with 'actions' key containing available planner actions
    """
    return PolicyLoader(path_resolver).load_available_actions()


# ID: 3a8f9608-e628-48d8-9139-fe297447971e
def load_micro_proposal_policy(path_resolver: PathResolver) -> dict[str, Any]:
    """
    Load micro-proposal policy using PathResolver.

    Args:
        path_resolver: PathResolver instance for .intent/ access

    Returns:
        Dict with 'policy_id' and 'rules' for micro-proposal validation
    """
    return PolicyLoader(path_resolver).load_micro_proposal_policy()


__all__ = ["PolicyLoader", "load_available_actions", "load_micro_proposal_policy"]
