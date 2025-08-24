# src/system/governance/checks/proposal_checks.py
"""
Orchestrates all proposal-related checks by delegating to specialized,
injected dependencies. This adheres to Dependency Injection principles for
better modularity and testability.
"""
from __future__ import annotations

from .proposal_loader import ProposalLoader
from .proposal_signature_checker import ProposalSignatureChecker
from .proposal_summarizer import ProposalSummarizer
from .proposal_validator import ProposalValidator


class ProposalChecks:
    """Container for proposal-related constitutional checks."""

    def __init__(
        self,
        loader: ProposalLoader,
        validator: ProposalValidator,
        signature_checker: ProposalSignatureChecker,
        summarizer: ProposalSummarizer,
    ):
        """Initializes the check with shared, injected dependencies."""
        self.loader = loader
        self.validator = validator
        self.signature_checker = signature_checker
        self.summarizer = summarizer

    # CAPABILITY: audit.check.proposals_schema
    def check_proposal_files_match_schema(self) -> list:
        """Validate each cr-*.yaml/json proposal against proposal.schema.json."""
        return self.validator.validate_proposals_schema(self.loader)

    # CAPABILITY: audit.check.proposals_drift
    def check_signatures_match_content(self) -> list:
        """
        Detect content/signature drift:
        - warn if a proposal has no signatures
        - warn if any signature token does not match the current content
        """
        return self.signature_checker.check_signatures_match_content(self.loader)

    # CAPABILITY: audit.check.proposals_list
    def list_pending_proposals(self) -> list:
        """Emit a friendly summary of pending proposals."""
        return self.summarizer.list_pending_proposals(self.loader)
