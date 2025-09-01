# src/system/governance/checks/proposal_loader.py
"""
Handles the discovery and loading of constitutional proposal files from disk.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml


# CAPABILITY: system.proposal.load
class ProposalLoader:
    """Handles loading and discovery of proposal files."""

    # CAPABILITY: system.proposal.loader.initialize
    def __init__(self, proposals_dir: Path, repo_root: Path):
        """Initialize the instance with paths to the proposals directory and repository root."""
        self.proposals_dir = proposals_dir
        self.repo_root = repo_root

    # CAPABILITY: system.proposal.discover_paths
    def _proposal_paths(self) -> list[Path]:
        """Return all cr-* proposals (both YAML and JSON)."""
        if not self.proposals_dir.exists():
            return []
        return sorted(
            list(self.proposals_dir.glob("cr-*.yaml"))
            + list(self.proposals_dir.glob("cr-*.yml"))
            + list(self.proposals_dir.glob("cr-*.json"))
        )

    # CAPABILITY: system.proposal.load
    def _load_proposal(self, path: Path) -> dict:
        """Load proposal preserving its format."""
        try:
            text = path.read_text(encoding="utf-8")
            if path.suffix.lower() == ".json":
                return json.loads(text) or {}
            return yaml.safe_load(text) or {}
        except Exception as e:  # surface upstream with path context
            raise ValueError(f"parse error: {e}") from e
