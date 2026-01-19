# src/body/cli/commands/refactor_support/config.py

"""
Configuration and file enumeration for refactoring analysis.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from mind.governance.enforcement_loader import EnforcementMappingLoader
from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 15dff2fb-d1d0-4d85-9fb8-7667e5b93b40
def get_modularity_threshold() -> float:
    """
    Retrieves the authoritative 'max_score' from the Constitution.
    Path: .intent/enforcement/mappings/architecture/modularity.yaml
    """
    try:
        loader = EnforcementMappingLoader(settings.REPO_PATH / ".intent")
        strategy = loader.get_enforcement_strategy(
            "modularity.refactor_score_threshold"
        )
        if strategy and "params" in strategy:
            return float(strategy["params"].get("max_score", 60.0))
    except Exception as e:
        logger.debug("Could not load modularity threshold from Constitution: %s", e)

    return 60.0  # Safe fallback


# ID: f54112b9-6914-4af4-9f38-087b8837db95
def get_source_files() -> Iterable[Path]:
    """
    Standardized file enumerator. Ensures we don't analyze junk/temp folders.
    """
    skip_dirs = {
        ".venv",
        "venv",
        ".git",
        "work",
        "var",
        "__pycache__",
        ".pytest_cache",
        "tests",
        "migrations",
        "reports",
    }
    src_root = settings.REPO_PATH / "src"
    if not src_root.exists():
        return []

    for file in src_root.rglob("*.py"):
        if any(part in file.parts for part in skip_dirs):
            continue
        yield file
