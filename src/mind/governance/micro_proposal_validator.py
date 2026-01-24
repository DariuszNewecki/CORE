# src/mind/governance/micro_proposal_validator.py

"""
Provides functionality for the micro_proposal_validator module.
Validates automated micro-proposals against the agent governance policy.
"""

from __future__ import annotations

from fnmatch import fnmatch
from typing import Any

import yaml

from shared.logger import getLogger
from shared.path_resolver import PathResolver


logger = getLogger(__name__)


def _default_policy() -> dict[str, Any]:
    """
    Safe defaults:
      - allow typical repo paths
      - forbid anything under .intent/**
    """
    return {
        "rules": [
            {
                "id": "safe_paths",
                "allowed_paths": [
                    "src/**",
                    "tests/**",
                    "docs/**",
                    "**/*.md",
                    "**/*.py",
                ],
                "forbidden_paths": [".intent/**"],
            },
            {
                "id": "safe_actions",
                "allowed_actions": [],  # Default to allowing nothing if policy fails
            },
        ]
    }


def _load_policy(path_resolver: PathResolver) -> dict[str, Any]:
    """Loads the agent_governance.yaml policy via PathResolver."""
    try:
        policy_path = path_resolver.policy("agent_governance")
        if policy_path.exists():
            data = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
        else:
            raise FileNotFoundError(str(policy_path))

        # Extract specific micro_proposals lane
        lanes = data.get("autonomy_lanes", {}).get("micro_proposals", {})

        if not lanes:
            logger.warning(
                "'autonomy_lanes.micro_proposals' missing in agent_governance.yaml"
            )
            return _default_policy()

        return {
            "policy_id": data.get("policy_id"),
            "rules": [
                {
                    "id": "safe_paths",
                    "allowed_paths": lanes.get("safe_paths", []),
                    "forbidden_paths": lanes.get("forbidden_paths", []),
                },
                {
                    "id": "safe_actions",
                    "allowed_actions": lanes.get("allowed_actions", []),
                },
            ],
        }
    except Exception as e:
        logger.error("Failed to load micro proposal policy: %s", e)
        return _default_policy()


# ID: 6928ebf9-9495-4193-a1aa-ef064f6bb189
class MicroProposalValidator:
    """
    Minimal, deterministic validator:
      - no file I/O
      - enforces allowed/forbidden paths
      - enforces allowed actions
      - wording matches test expectations
    """

    def __init__(self, path_resolver: PathResolver):
        self._path_resolver = path_resolver
        self.policy: dict[str, Any] = _load_policy(self._path_resolver)

        # Extract Paths Rule
        path_rule = next(
            (r for r in self.policy.get("rules", []) if r.get("id") == "safe_paths"), {}
        )
        self._allowed_paths: list[str] = list(path_rule.get("allowed_paths", []) or [])
        self._forbidden_paths: list[str] = list(
            path_rule.get("forbidden_paths", []) or []
        )

        # Extract Actions Rule (FIXED: Added this)
        action_rule = next(
            (r for r in self.policy.get("rules", []) if r.get("id") == "safe_actions"),
            {},
        )
        self._allowed_actions: list[str] = list(
            action_rule.get("allowed_actions", []) or []
        )

    def _path_ok(self, file_path: str) -> tuple[bool, str]:
        for pat in self._forbidden_paths:
            if fnmatch(file_path, pat):
                return (False, f"Path '{file_path}' is explicitly forbidden by policy")

        if self._allowed_paths and (
            not any(fnmatch(file_path, pat) for pat in self._allowed_paths)
        ):
            return (False, f"Path '{file_path}' not in allowed paths")

        return (True, "ok")

    def _action_ok(self, action: str) -> tuple[bool, str]:
        if not self._allowed_actions:
            return (True, "ok")  # If no list defined, assume permissive or default

        if action not in self._allowed_actions:
            return (False, f"Action '{action}' is not in the allowed autonomy lane")

        return (True, "ok")

    # ID: a74c44cb-be1f-41fa-ad5c-13bd09602fd7
    def validate(self, plan: list[Any]) -> tuple[bool, str]:
        """
        Lightweight validation used before execution.
        Accepts Pydantic objects (with .model_dump()) or plain dicts.
        """
        if not isinstance(plan, list) or not plan:
            return (False, "Plan is empty")

        for idx, step in enumerate(plan, 1):
            step_dict = step.model_dump() if hasattr(step, "model_dump") else dict(step)

            # 1. Validate Action
            action = step_dict.get("action") or step_dict.get("name")
            if not action:
                return (False, f"Step {idx} missing action")

            action_ok, action_msg = self._action_ok(action)
            if not action_ok:
                return (False, action_msg)

            # 2. Validate Path (if applicable)
            params = step_dict.get("parameters") or step_dict.get("params") or {}
            file_path = params.get("file_path")

            if isinstance(file_path, str):
                path_ok, path_msg = self._path_ok(file_path)
                if not path_ok:
                    return (False, path_msg)

        return (True, "")
