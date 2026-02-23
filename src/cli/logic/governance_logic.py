# src/body/cli/logic/governance_logic.py

"""
Engine logic for constitutional governance reporting.
Headless redirector for V2.3 Octopus Synthesis.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .governance import ensure_coverage_map, renderer


# ID: 64b1509a-d090-4e54-9afb-545edec329db
def get_coverage_data(repo_root: Path, file_handler: Any) -> dict[str, Any]:
    """Authoritative entry point to get coverage data."""
    map_path = ensure_coverage_map(repo_root, file_handler)
    import json

    with map_path.open(encoding="utf-8") as f:
        return json.load(f)


# ID: 3f4a9774-4080-4be0-9ab3-8473187b62f7
def render_summary(coverage_data: dict[str, Any]) -> str:
    return renderer.render_summary(coverage_data)


# ID: 223508d6-92b3-451e-8aed-a9930471db3b
def render_hierarchical(coverage_data: dict[str, Any]) -> str:
    return renderer.render_hierarchical(coverage_data)
