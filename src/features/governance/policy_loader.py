# src/features/governance/policy_loader.py
"""
Centralized loaders for constitution-backed policies used by agents and services.
- Avoids hardcoding actions/params in code.
- Keeps a single source of truth for Planner/ExecutionAgent validation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

try:
    # Use shared logger per logging policy (no direct logging import/print)
    from shared.logger import getLogger  # type: ignore
except Exception:  # Fallback if logger import path changes during refactors

    # ID: c9da80fe-4c0b-4e9b-aaa0-b8acfa2dec86
    def getLogger(name: str):  # type: ignore
        class _Nop:
            def __getattr__(self, _):  # noqa: D401
                def _noop(*__, **___):
                    return None

                return _noop

        return _Nop()


log = getLogger(__name__)

# Constitution paths (governance policies)
GOVERNANCE_DIR = Path(".intent/charter/policies/governance")

_AVAILABLE_ACTIONS_FILE = GOVERNANCE_DIR / "available_actions_policy.yaml"
_MICRO_PROPOSAL_FILE = GOVERNANCE_DIR / "micro_proposal_policy.yaml"


def _load_yaml(path: Path) -> Dict[str, Any]:
    """
    Load a YAML file and return a dict. Raises ValueError with a clear message on failure.
    """
    if not path.exists():
        msg = f"Policy file not found: {path}"
        log.error(msg)
        raise ValueError(msg)
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                msg = f"Policy file must deserialize to a mapping: {path}"
                log.error(msg)
                raise ValueError(msg)
            return data
    except Exception as e:  # noqa: BLE001
        msg = f"Failed to load policy YAML: {path} ({e})"
        log.error(msg)
        raise ValueError(msg) from e


# ID: b843e5d2-401f-4271-8a47-6d722de9b8ce
def load_available_actions() -> Dict[str, Any]:
    """
    Load the canonical list of available actions for the PlannerAgent.
    Source: .intent/charter/policies/governance/available_actions_policy.yaml
    """
    policy = _load_yaml(_AVAILABLE_ACTIONS_FILE)
    # Basic structure sanity checks (keep lightweight to avoid tight coupling)
    actions = policy.get("actions")
    if not isinstance(actions, list) or not actions:
        msg = f"'actions' must be a non-empty list in {_AVAILABLE_ACTIONS_FILE}"
        log.error(msg)
        raise ValueError(msg)
    return policy


# ID: 29d61bb4-8fdc-42e9-9d1c-30cae93a9e10
def load_micro_proposal_policy() -> Dict[str, Any]:
    """
    Load the Micro-Proposal Policy (Autonomous Fast Track) used for path guardrails.
    Source: .intent/charter/policies/governance/micro_proposal_policy.yaml
    """
    policy = _load_yaml(_MICRO_PROPOSAL_FILE)
    rules = policy.get("rules")
    if not isinstance(rules, list) or not rules:
        msg = f"'rules' must be a non-empty list in {_MICRO_PROPOSAL_FILE}"
        log.error(msg)
        raise ValueError(msg)
    return policy


__all__ = [
    "load_available_actions",
    "load_micro_proposal_policy",
]
