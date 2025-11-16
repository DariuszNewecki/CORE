# src/mind/governance/policy_loader.py

"""
Centralized loaders for constitution-backed policies used by agents and services.
- Avoids hardcoding actions/params in code.
- Keeps a single source of truth for Planner/ExecutionAgent validation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from shared.config import settings
from shared.logger import getLogger

logger = getLogger(__name__)

CONSTITUTION_DIR = Path(".intent/charter")
GOVERNANCE_DIR = CONSTITUTION_DIR / "policies" / "governance"
AGENT_DIR = CONSTITUTION_DIR / "policies" / "agent"


def _load_policy_yaml(path: Path) -> dict[str, Any]:
    """
    Loads and performs basic validation on a policy YAML file.
    Resolves relative paths based on settings.REPO_PATH.
    """
    if not path.is_absolute():
        path = settings.REPO_PATH / path
    if not path.exists():
        msg = f"Policy file not found: {path}"
        logger.error(msg)
        raise ValueError(msg)
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            msg = f"Policy file must be a dictionary: {path}"
            logger.error(msg)
            raise ValueError(msg)
        return data
    except Exception as e:
        msg = f"Failed to load policy YAML: {path} ({e})"
        logger.error(msg)
        raise ValueError(msg) from e


# ID: 5477bdaa-1466-405a-a8a8-50d15020ebf9
def load_available_actions() -> dict[str, Any]:
    """
    Load the canonical list of available actions for the PlannerAgent.
    """
    policy_path = GOVERNANCE_DIR / "available_actions_policy.yaml"
    policy = _load_policy_yaml(policy_path)
    actions = policy.get("actions")
    if not isinstance(actions, list) or not actions:
        raise ValueError("'actions' must be a non-empty list in the policy.")
    return policy


# ID: d921aae8-c492-4e39-9aba-d5d2ad89af09
def load_micro_proposal_policy() -> dict[str, Any]:
    """
    Load the Micro-Proposal Policy for autonomous path guardrails.
    """
    policy_path = AGENT_DIR / "micro_proposal_policy.yaml"
    policy = _load_policy_yaml(policy_path)
    rules = policy.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("'rules' must be a non-empty list in the policy.")
    return policy


__all__ = ["load_available_actions", "load_micro_proposal_policy"]
