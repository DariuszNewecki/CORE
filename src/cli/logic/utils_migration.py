# src/system/admin/utils_migration.py
"""
Shared utilities for constitutional migration and domain rationalization.
This is the canonical location for logic used by migration-related tools.
"""

from __future__ import annotations

import re
from pathlib import Path

from rich.console import Console
from ruamel.yaml import YAML

yaml_handler = YAML()
yaml_handler.preserve_quotes = True
yaml_handler.indent(mapping=2, sequence=4, offset=2)


# ID: 64bb309f-1cf9-4480-afc4-78130e8357e2
def parse_migration_plan(plan_path: Path) -> dict[str, str]:
    """Parses the markdown migration plan into a mapping dictionary."""
    if not plan_path.exists():
        raise FileNotFoundError(f"Migration plan not found at: {plan_path}")
    content = plan_path.read_text(encoding="utf-8")
    pattern = re.compile(r"\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|")
    matches = pattern.findall(content)
    if not matches:
        raise ValueError("No valid domain mappings found in the migration plan.")
    return {old.strip(): new.strip() for old, new in matches}


# ID: 80131c72-c024-4823-8226-f63c5d8c4704
def replacer(
    match: re.Match, domain_map: dict, console: Console, py_file: Path, repo_root: Path
) -> str:
    """Replacement function for re.subn to update capability tags."""
    old_cap = match.group(1)
    for old_domain, new_domain in domain_map.items():
        if old_cap.startswith(old_domain):
            new_cap = old_cap.replace(old_domain, new_domain, 1)
            if old_cap != new_cap:
                console.print(
                    f"   -> In '{py_file.relative_to(repo_root)}': Renaming tag '{old_cap}' -> '[green]{new_cap}[/green]'"
                )
    return match.group(0)
