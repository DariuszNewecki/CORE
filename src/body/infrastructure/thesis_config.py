# src/body/infrastructure/thesis_config.py
"""The thesis sensor's settings, read where settings may be read."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
# ID: 3d73eab9-4f40-4f42-9466-9d09c3c24da0
class ThesisConfig:
    """GitHub repository and token, Claude Code's transcripts, the
    governor's GitHub login (None when it cannot be read), the deploy ledger
    and the post-merge runner's logs."""

    repo: str
    token: str | None
    transcripts: Path
    governor: str | None = None
    deploy_ledger: Path = Path("/opt/core/deploy-ledger.jsonl")
    pipeline_logs: Path = Path("/var/lib/core-pipeline/logs")


# ID: adac3300-9fe2-4840-93a5-34be0edb8499
def pipeline_governor(conf: Path) -> str | None:
    """GOVERNOR_GITHUB from the runner's KEY=VALUE pipeline.conf, parsed as
    the runner's read_conf does; None when the file cannot be read."""
    try:
        lines = conf.read_text().splitlines()
    except OSError:
        return None
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            if key.strip() == "GOVERNOR_GITHUB":
                return value.strip().strip('"') or None
    return None


# ID: 5e3408ba-5bab-4bac-bf1c-75806d311ae9
def thesis_config() -> ThesisConfig:
    """CORE_GITHUB_REPO, CORE_GITHUB_TOKEN, CORE_CLAUDE_TRANSCRIPTS,
    CORE_GOVERNOR_GITHUB or else the runner's GOVERNOR_GITHUB,
    CORE_DEPLOY_LEDGER and CORE_PIPELINE_LOGS."""
    from shared.config import settings

    return ThesisConfig(
        settings.CORE_GITHUB_REPO,
        settings.CORE_GITHUB_TOKEN,
        Path(settings.CORE_CLAUDE_TRANSCRIPTS),
        settings.CORE_GOVERNOR_GITHUB
        or pipeline_governor(Path(settings.CORE_PIPELINE_CONF)),
        Path(settings.CORE_DEPLOY_LEDGER),
        Path(settings.CORE_PIPELINE_LOGS),
    )
