# src/mind/governance/micro_proposal_validator.py

"""Provides functionality for the micro_proposal_validator module."""

from __future__ import annotations

from fnmatch import fnmatch
from typing import Any

from shared.config import settings
from shared.logger import getLogger


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
            }
        ]
    }


# ID: 6928ebf9-9495-4193-a1aa-ef064f6bb189
class MicroProposalValidator:
    """
    Minimal, deterministic validator:
      - no file I/O
      - enforces allowed/forbidden paths
      - wording matches test expectations
    """

    def __init__(self):
        self.policy: dict[str, Any] = settings.load(
            "charter.policies.agent.micro_proposal_policy"
        )
        rule = next(
            (r for r in self.policy.get("rules", []) if r.get("id") == "safe_paths"), {}
        )
        self._allowed: list[str] = list(rule.get("allowed_paths", []) or [])
        self._forbidden: list[str] = list(rule.get("forbidden_paths", []) or [])

    def _path_ok(self, file_path: str) -> tuple[bool, str]:
        for pat in self._forbidden:
            if fnmatch(file_path, pat):
                return (False, f"Path '{file_path}' is explicitly forbidden by policy")
        if self._allowed and (
            not any(fnmatch(file_path, pat) for pat in self._allowed)
        ):
            return (False, f"Path '{file_path}' not in allowed paths")
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
            action = step_dict.get("action") or step_dict.get("name")
            if not action:
                return (False, f"Step {idx} missing action")
            params = step_dict.get("parameters") or step_dict.get("params") or {}
            file_path = params.get("file_path")
            if isinstance(file_path, str):
                ok, msg = self._path_ok(file_path)
                if not ok:
                    return (False, msg)
        return (True, "")
