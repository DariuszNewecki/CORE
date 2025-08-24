# src/system/governance/checks/proposal_signature_checker.py
"""
Validates proposal file signatures and detects content drift against those signatures.
"""

from __future__ import annotations

import hashlib

from system.governance.models import AuditFinding, AuditSeverity

from .proposal_loader import ProposalLoader


class ProposalSignatureChecker:
    """Handles signature validation and content drift detection for proposals."""

    @staticmethod
    def _expected_token_for_content(content: str) -> str:
        """Mirror admin token format: 'core-proposal-v1:<sha256hex>'."""
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return f"core-proposal-v1:{digest}"

    def check_signatures_match_content(
        self, loader: ProposalLoader
    ) -> list[AuditFinding]:
        """
        Detect content/signature drift:
        - warn if a proposal has no signatures
        - warn if any signature token does not match the current content
        """
        findings: list[AuditFinding] = []
        check_name = "Proposals: Signature ↔ Content Drift"

        for path in loader._proposal_paths():
            rel = str(path.relative_to(loader.repo_root))
            try:
                data = loader._load_proposal(path)
            except ValueError as e:
                findings.append(
                    AuditFinding(
                        AuditSeverity.ERROR,
                        f"{path.name}: {e}",
                        check_name,
                        rel,
                    )
                )
                continue

            content = data.get("content", "")
            expected = self._expected_token_for_content(content)
            signatures = data.get("signatures", [])

            if not signatures:
                findings.append(
                    AuditFinding(
                        AuditSeverity.WARNING,
                        f"{path.name}: no signatures present.",
                        check_name,
                        rel,
                    )
                )
                continue

            mismatches = [s for s in signatures if s.get("token") != expected]
            if mismatches:
                identities = ", ".join(
                    s.get("identity", "<unknown>") for s in mismatches
                )
                findings.append(
                    AuditFinding(
                        AuditSeverity.WARNING,
                        f"{path.name}: {len(mismatches)} signature(s) do not match current content "
                        f"(likely edited after signing). Identities: {identities}",
                        check_name,
                        rel,
                    )
                )
            else:
                findings.append(
                    AuditFinding(
                        AuditSeverity.SUCCESS,
                        f"{path.name}: all signatures match current content.",
                        check_name,
                        rel,
                    )
                )

        if not findings and not loader._proposal_paths():
            # nothing to report if there are no proposals
            return []

        return findings
