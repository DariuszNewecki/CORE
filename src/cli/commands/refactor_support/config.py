# src/cli/commands/refactor_support/config.py

"""Configuration and file enumeration for refactoring analysis.

`get_modularity_threshold` thinly wraps GET /v1/refactor/threshold so the
CLI doesn't reach into `mind.governance.enforcement_loader` directly.
`get_source_files` stays as a stdlib filesystem walk — pure local
enumeration, no CORE-internal imports.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

from api.cli import CoreApiClient


logger = logging.getLogger(__name__)


# ID: 15dff2fb-d1d0-4d85-9fb8-7667e5b93b40
async def get_modularity_threshold(repo_root: Path | None = None) -> float:
    """Retrieve the authoritative `max_score` from the constitution via API.

    `repo_root` retained for call-site compatibility; the API resolves
    the repo root server-side now.
    """
    _ = repo_root
    try:
        client = CoreApiClient()
        payload = await client.refactor_threshold()
        return float(payload.get("threshold", 60.0))
    except Exception as exc:
        logger.debug(
            "refactor.config: could not load modularity threshold via API: %s", exc
        )
        return 60.0


# ID: f54112b9-6914-4af4-9f38-087b8837db95
def get_source_files(repo_root: Path) -> Iterable[Path]:
    """Standardized file enumerator. Filters junk/temp folders.

    Pure local filesystem walk — no CORE-internal imports.
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
    src_root = repo_root / "src"
    if not src_root.exists():
        return []

    for file in src_root.rglob("*.py"):
        if any(part in file.parts for part in skip_dirs):
            continue
        yield file
