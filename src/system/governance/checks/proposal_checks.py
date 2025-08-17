# src/system/governance/checks/proposal_checks.py
"""Auditor checks for proposal formats and drift in .intent/proposals/."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
import yaml

from shared.schemas.manifest_validator import load_schema
from system.governance.models import AuditFinding, AuditSeverity


class ProposalChecks:
    """Container for proposal-related constitutional checks."""

    def __init__(self, context):
        """Initializes the check with a shared auditor context, setting `repo_root` and `proposals_dir` paths."""
        """Initializes the check with a shared auditor context."""
        self.context = context
        self.repo_root: Path = context.repo_root
        self.proposals_dir: Path = self.repo_root / ".intent" / "proposals"

    # --- helpers -------------------------------------------------------------

    def _proposal_paths(self) -> list[Path]:
        """Return all cr-* proposals (both YAML and JSON)."""
        if not self.proposals_dir.exists():
            return []
        return sorted(
            list(self.proposals_dir.glob("cr-*.yaml"))
            + list(self.proposals_dir.glob("cr-*.yml"))
            + list(self.proposals_dir.glob("cr-*.json"))
        )

    """Loads a proposal from a JSON or YAML file at the given path, returning an empty dict on parse failure or empty content."""

    def _load_proposal(self, path: Path) -> dict:
        """Load proposal preserving its format."""
        try:
            text = path.read_text(encoding="utf-8")
            if path.suffix.lower() == ".json":
                return json.loads(text) or {}
            return yaml.safe_load(text) or {}
        except Exception as e:  # surface upstream with path context
            raise ValueError(f"parse error: {e}") from e

    @staticmethod
    def _expected_token_for_content(content: str) -> str:
        """Mirror admin token format: 'core-proposal-v1:<sha256hex>'."""
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return f"core-proposal-v1:{digest}"

    # --- checks --------------------------------------------------------------

    """Validate each cr-*.yaml/json proposal against proposal.schema.json, returning a list of AuditFindings for compliance or errors."""

    # CAPABILITY: audit.check.proposals_schema
    def check_proposal_files_match_schema(self) -> list[AuditFinding]:
        """Validate each cr-*.yaml/json proposal against proposal.schema.json."""
        findings: list[AuditFinding] = []
        check_name = "Proposals: Schema Compliance"

        paths = self._proposal_paths()
        if not paths:
            if not self.proposals_dir.exists():
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
                data = self._load_proposal(path)
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

    # CAPABILITY: audit.check.proposals_drift
    def check_signatures_match_content(self) -> list[AuditFinding]:
        """
        Detect content/signature drift:
        - warn if a proposal has no signatures
        - warn if any signature token does not match the current content
        """
        findings: list[AuditFinding] = []
        check_name = "Proposals: Signature ↔ Content Drift"

        for path in self._proposal_paths():
            rel = str(path.relative_to(self.repo_root))
            try:
                data = self._load_proposal(path)
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

        if not findings and not self._proposal_paths():
            # nothing to report if there are no proposals
            return []

        return findings
        """Return a list of AuditFinding objects summarizing pending proposals, including their paths and severity."""

    # CAPABILITY: audit.check.proposals_list
    def list_pending_proposals(self) -> list[AuditFinding]:
        """Emit a friendly summary of pending proposals."""
        findings: list[AuditFinding] = []
        check_name = "Proposals: Pending Summary"

        paths = self._proposal_paths()
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
