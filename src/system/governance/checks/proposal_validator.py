# src/system/governance/checks/proposal_validator.py
"""
Validates proposal files against JSON schema to ensure structural and data integrity.
"""

from __future__ import annotations

from pathlib import Path

import jsonschema

from shared.schemas.manifest_validator import load_schema
from system.governance.models import AuditFinding, AuditSeverity

from .proposal_loader import ProposalLoader


# CAPABILITY: system.proposal.validate_schema
class ProposalValidator:
    """Handles schema validation of proposal files."""

    # CAPABILITY: system.proposal.validator.initialize
    def __init__(self, repo_root: Path):
        """Initializes the instance with the provided repository root path."""
        self.repo_root = repo_root

    # CAPABILITY: audit.check.proposals_schema
    def validate_proposals_schema(self, loader: ProposalLoader) -> list[AuditFinding]:
        """Validate each cr-*.yaml/json proposal against proposal.schema.json."""
        findings: list[AuditFinding] = []
        check_name = "Proposals: Schema Compliance"

        paths = loader._proposal_paths()
        if not paths:
            if not loader.proposals_dir.exists():
                findings.append(
                    AuditFinding(
                        AuditSeverity.SUCCESS,
                        "No proposals directory found; nothing to validate.",
                        check_name,
                    )
                )
            else:
                findings.append(
                    AuditFinding(
                        AuditSeverity.SUCCESS,
                        "No pending proposals found.",
                        check_name,
                    )
                )
            return findings

        schema = load_schema("proposal.schema.json")
        validator = jsonschema.Draft7Validator(schema)

        for path in paths:
            rel = str(path.relative_to(self.repo_root))
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

            errors = list(validator.iter_errors(data))
            if errors:
                for err in errors:
                    loc = ".".join(str(p) for p in err.absolute_path) or "<root>"
                    findings.append(
                        AuditFinding(
                            AuditSeverity.ERROR,
                            f"{path.name}: {loc} -> {err.message}",
                            check_name,
                            rel,
                        )
                    )
            else:
                findings.append(
                    AuditFinding(
                        AuditSeverity.SUCCESS,
                        f"{path.name} conforms to proposal.schema.json",
                        check_name,
                        rel,
                    )
                )

        return findings
