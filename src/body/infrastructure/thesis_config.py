# src/body/infrastructure/thesis_config.py
"""The thesis sensor's settings, read where settings may be read."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
# ID: 3d73eab9-4f40-4f42-9466-9d09c3c24da0
class ThesisConfig:
    """GitHub repository and token, and Claude Code's transcripts."""

    repo: str
    token: str | None
    transcripts: Path


# ID: 5e3408ba-5bab-4bac-bf1c-75806d311ae9
def thesis_config() -> ThesisConfig:
    """CORE_GITHUB_REPO, CORE_GITHUB_TOKEN and CORE_CLAUDE_TRANSCRIPTS."""
    from shared.config import settings

    return ThesisConfig(
        settings.CORE_GITHUB_REPO,
        settings.CORE_GITHUB_TOKEN,
        Path(settings.CORE_CLAUDE_TRANSCRIPTS),
    )
