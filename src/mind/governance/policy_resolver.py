# src/mind/governance/policy_resolver.py

"""Provides functionality for the policy_resolver module."""

from __future__ import annotations

import glob
import os

import yaml


POLICY_ROOT = os.getenv("CORE_POLICY_ROOT", ".intent")


def _scan() -> list[str]:
    return glob.glob(os.path.join(POLICY_ROOT, "**", "*_policy.yaml"), recursive=True)


# ID: c4fd0016-61be-4591-ae8c-38ad05fc4d97
def resolve_policy(*, policy_id: str | None = None, filename: str | None = None) -> str:
    """
    Resolve a policy by YAML 'id' or by filename (basename only).
    Does NOT depend on old directory layout. Raises ValueError if not found.
    """
    candidates = _scan()

    if filename:
        base = os.path.basename(filename)
        for p in candidates:
            if os.path.basename(p) == base:
                return p

    if policy_id:
        for p in candidates:
            try:
                with open(p, encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                if data.get("id") == policy_id:
                    return p
            except Exception:
                pass

    raise ValueError(
        f"Policy not found (policy_id={policy_id!r}, filename={filename!r}) under {POLICY_ROOT}"
    )
