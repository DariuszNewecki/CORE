# src/body/cli/logic/proposals/canary.py

"""Refactored logic for src/body/cli/logic/proposals/canary.py."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from mind.governance.audit_context import AuditorContext
from mind.governance.auditor import ConstitutionalAuditor
from shared.infrastructure.storage.file_handler import FileHandler


# ID: 1c07f2d4-cfdb-4ece-bbe2-3cf6c0c449a8
async def run_canary_audit(
    repo_root: Path, fs: FileHandler, proposal: dict[str, Any], proposal_name: str
) -> tuple[bool, list[Any]]:
    """Creates a canary environment and runs the full audit."""
    target_rel_path = str(proposal["target_path"]).lstrip("./")
    canary_root_rel = f"var/workflows/canary/{proposal_name}/repo"

    fs.remove_tree(f"var/workflows/canary/{proposal_name}")
    fs.ensure_dir(f"var/workflows/canary/{proposal_name}")
    fs.copy_repo_snapshot(
        canary_root_rel, exclude_top_level=("var", ".git", "__pycache__", ".venv")
    )
    fs.write_runtime_text(
        f"{canary_root_rel}/{target_rel_path}", proposal.get("content", "")
    )

    canary_root_abs = repo_root / canary_root_rel
    env_file = canary_root_abs / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file, override=True)

    auditor_context = AuditorContext(canary_root_abs)
    findings = await ConstitutionalAuditor(auditor_context).run_full_audit_async()

    def _is_blocking(finding: Any) -> bool:
        severity = getattr(finding, "severity", None)
        if hasattr(severity, "is_blocking"):
            return bool(severity.is_blocking)
        if isinstance(severity, str):
            return severity.lower() == "error"
        if isinstance(finding, dict):
            return str(finding.get("severity", "")).lower() == "error"
        return False

    return not any(_is_blocking(f) for f in findings), findings
