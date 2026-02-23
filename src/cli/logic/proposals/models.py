# src/body/cli/logic/proposals/models.py

"""Provides functionality for the models module."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
# ID: 5cc2a437-a17b-421c-b074-5eeacefdba80
class ProposalInfo:
    """Represents the status of a single proposal."""

    name: str
    justification: str
    target_path: str
    status: str
    is_critical: bool
    current_sigs: int
    required_sigs: int


def _yaml_dump(payload: dict[str, Any]) -> str:
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)


def _to_repo_rel(repo_root: Path, abs_path: Path) -> str:
    abs_path, repo_root = abs_path.resolve(), repo_root.resolve()
    try:
        return str(abs_path.relative_to(repo_root))
    except Exception as e:
        raise ValueError(f"Path is not within repo root: {abs_path}") from e
