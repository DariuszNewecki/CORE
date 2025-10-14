# src/features/governance/policy_loader.py
"""
Centralized loaders for constitution-backed policies used by agents and services.
- Avoids hardcoding actions/params in code.
- Keeps a single source of truth for Planner/ExecutionAgent validation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from shared.logger import getLogger

log = getLogger(__name__)

# Define base paths relative to the assumed .intent directory structure
CONSTITUTION_DIR = Path(".intent/charter")
GOVERNANCE_DIR = CONSTITUTION_DIR / "policies" / "governance"
AGENT_DIR = CONSTITUTION_DIR / "policies" / "agent"


def _load_policy_yaml(path: Path) -> dict[str, Any]:
    """
    Loads and performs basic validation on a policy YAML file.
    This is now the single source of truth for loading these policies.
    """
    if not path.exists():
        msg = f"Policy file not found: {path}"
        log.error(msg)
        raise ValueError(msg)
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            msg = f"Policy file must be a dictionary: {path}"
            log.error(msg)
            raise ValueError(msg)
        return data
    except Exception as e:
        msg = f"Failed to load policy YAML: {path} ({e})"
        log.error(msg)
        raise ValueError(msg) from e


# ID: b843e5d2-401f-4271-8a47-6d722de9b8ce
def load_available_actions() -> dict[str, Any]:
    """
    Load the canonical list of available actions for the PlannerAgent.
    """
    policy = _load_policy_yaml(GOVERNANCE_DIR / "available_actions_policy.yaml")
    actions = policy.get("actions")
    if not isinstance(actions, list) or not actions:
        raise ValueError("'actions' must be a non-empty list in the policy.")
    return policy


# ID: 29d61bb4-8fdc-42e9-9d1c-30cae93a9e10
def load_micro_proposal_policy() -> dict[str, Any]:
    """
    Load the Micro-Proposal Policy for autonomous path guardrails.
    """
    policy = _load_policy_yaml(AGENT_DIR / "micro_proposal_policy.yaml")
    rules = policy.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("'rules' must be a non-empty list in the policy.")
    return policy


__all__ = [
    "load_available_actions",
    "load_micro_proposal_policy",
]
