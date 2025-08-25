# src/system/governance/checks/proposal_summarizer.py
"""
Handles the summarization and listing of pending proposals.
"""

from __future__ import annotations

from pathlib import Path

from system.governance.models import AuditFinding, AuditSeverity

from .proposal_loader import ProposalLoader


class ProposalSummarizer:
    """Provides a summary of pending proposals."""

    def __init__(self, proposals_dir: Path, repo_root: Path):
        """Initializes the summarizer with necessary path information."""
        self.proposals_dir = proposals_dir
        self.repo_root = repo_root

    def list_pending_proposals(self, loader: ProposalLoader) -> list[AuditFinding]:
        """Emit a friendly summary of pending proposals."""
        check_name = "Proposals: Pending Summary"
        findings: list[AuditFinding] = []

        paths = loader._proposal_paths()
        if not paths:
            if self.proposals_dir.exists():
                findings.append(
                    AuditFinding(
                        AuditSeverity.SUCCESS,
                        "No pending proposals.",
                        check_name,
                    )
                )
            return findings

        for path in paths:
            findings.append(
                AuditFinding(
                    AuditSeverity.WARNING,  # warning to make it visible in audit output
                    f"Pending proposal: {path.name}",
                    check_name,
                    str(path.relative_to(self.repo_root)),
                )
            )
        return findings
