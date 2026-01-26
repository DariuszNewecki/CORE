# src/mind/governance/policy_resolver.py

"""Provides functionality for the policy_resolver module."""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.path_resolver import PathResolver
from shared.utils.path_utils import iter_files_by_extension


def _get_policy_root() -> Path:
    """Get policy root from PathResolver (constitutional compliance)."""
    resolver = PathResolver()
    return resolver.intent_root


def _scan() -> list[Path]:
    """Scan for all policy YAML files in constitutional policy root."""
    root = _get_policy_root()
    all_yaml_files = iter_files_by_extension(root, (".yaml",), recursive=True)
    # Filter for *_policy.yaml files only
    return [f for f in all_yaml_files if f.name.endswith("_policy.yaml")]


# ID: c4fd0016-61be-4591-ae8c-38ad05fc4d97
def resolve_policy(*, policy_id: str | None = None, filename: str | None = None) -> str:
    """
    Resolve a policy by YAML 'id' or by filename (basename only).
    Uses PathResolver for constitutional compliance.
    """
    candidates = _scan()

    if filename:
        target_name = Path(filename).name
        for p in candidates:
            if p.name == target_name:
                return str(p)

    if policy_id:
        for p in candidates:
            try:
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                if data.get("id") == policy_id:
                    return str(p)
            except Exception:
                pass

    policy_root = _get_policy_root()
    raise ValueError(
        f"Policy not found (policy_id={policy_id!r}, filename={filename!r}) under {policy_root}"
    )
