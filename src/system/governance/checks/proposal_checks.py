# src/system/governance/checks/proposal_checks.py
"""Auditor checks for proposal formats and drift in .intent/proposals/."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import List

import jsonschema
import yaml

from shared.schemas.manifest_validator import load_schema
from system.governance.checks.base import BaseAuditCheck
from system.governance.models import AuditFinding, AuditSeverity


class ProposalChecks(BaseAuditCheck):
    """Container for proposal-related constitutional checks."""

    def __init__(self, context):
        """Initializes the check with a shared auditor context."""
        super().__init__(context)
        self.proposals_dir: Path = self.context.intent_dir / "proposals"
        try:
            self.proposal_schema = load_schema("proposal.schema.json")
        except Exception:
            self.proposal_schema = None

    # --- Private Helper Methods for Single-Responsibility ---

    def _get_proposal_paths(self) -> list[Path]:
        """Return all cr-* proposals (both YAML and JSON)."""
        if not self.proposals_dir.exists():
            return []
        return sorted(
            list(self.proposals_dir.glob("cr-*.yaml"))
            + list(self.proposals_dir.glob("cr-*.yml"))
            + list(self.proposals_dir.glob("cr-*.json"))
        )

    def _load_proposal(self, path: Path) -> dict:
        """Load proposal preserving its format, raising ValueError on failure."""
        try:
            text = path.read_text(encoding="utf-8")
            if path.suffix.lower() == ".json":
                return json.loads(text) or {}
            return yaml.safe_load(text) or {}
        except Exception as e:
            raise ValueError(f"parse error: {e}") from e

    # --- CHANGE 1: Replaced the old v1 token logic with the secure v2 logic ---
    @staticmethod
    def _expected_token_for_proposal(proposal: dict) -> str:
        """
        Produce a deterministic token for approvals bound to the full proposal intent.
        This logic MUST mirror the token generation in `src/system/admin/utils.py`.
        """
        payload = {
            "version": "v2",
            "target_path": proposal.get("target_path"),
            "action": proposal.get("action"),
            "content": proposal.get("content", ""),
        }
        digest = hashlib.sha256()
        digest.update(json.dumps(payload, sort_keys=True).encode("utf-8"))
        return f"core-proposal-v2:{digest.finalize().hex()}"

    def _validate_single_proposal_schema(
        self, path: Path, validator: jsonschema.Draft7Validator
    ) -> List[AuditFinding]:
        """Validates a single proposal file against the JSON schema."""
        findings = []
        rel_path = str(path.relative_to(self.context.repo_root))
        try:
            data = self._load_proposal(path)
            errors = list(validator.iter_errors(data))
            if errors:
                for err in errors:
                    loc = ".".join(str(p) for p in err.absolute_path) or "<root>"
                    findings.append(
                        AuditFinding(
                            AuditSeverity.ERROR,
                            f"{path.name}: {loc} -> {err.message}",
                            "Proposals: Schema Compliance",
                            rel_path,
                        )
                    )
            else:
                findings.append(
                    AuditFinding(
                        AuditSeverity.SUCCESS,
                        f"{path.name} conforms to proposal.schema.json",
                        "Proposals: Schema Compliance",
                        rel_path,
                    )
                )
        except ValueError as e:
            findings.append(
                AuditFinding(
                    AuditSeverity.ERROR,
                    f"{path.name}: {e}",
                    "Proposals: Schema Compliance",
                    rel_path,
                )
            )
        return findings

    def _validate_single_proposal_signatures(self, path: Path) -> List[AuditFinding]:
        """Validates the signatures of a single proposal file for drift."""
        findings = []
        rel_path = str(path.relative_to(self.context.repo_root))
        try:
            data = self._load_proposal(path)
            # --- CHANGE 2: Call the new v2 token generator method ---
            expected_token = self._expected_token_for_proposal(data)
            signatures = data.get("signatures", [])

            if not signatures:
                findings.append(
                    AuditFinding(
                        AuditSeverity.WARNING,
                        f"{path.name}: no signatures present.",
                        "Proposals: Signature ↔ Content Drift",
                        rel_path,
                    )
                )
                return findings

            mismatches = [s for s in signatures if s.get("token") != expected_token]
            if mismatches:
                identities = ", ".join(
                    s.get("identity", "<unknown>") for s in mismatches
                )
                findings.append(
                    AuditFinding(
                        AuditSeverity.WARNING,
                        f"{path.name}: {len(mismatches)} signature(s) do not match current content (likely edited after signing). Identities: {identities}",
                        "Proposals: Signature ↔ Content Drift",
                        rel_path,
                    )
                )
            else:
                findings.append(
                    AuditFinding(
                        AuditSeverity.SUCCESS,
                        f"{path.name}: all signatures match current content.",
                        "Proposals: Signature ↔ Content Drift",
                        rel_path,
                    )
                )

        except ValueError as e:
            findings.append(
                AuditFinding(
                    AuditSeverity.ERROR,
                    f"{path.name}: {e}",
                    "Proposals: Signature ↔ Content Drift",
                    rel_path,
                )
            )
        return findings

    # --- Public Check Methods (Orchestrators) ---

    # CAPABILITY: audit.check.proposals_schema
    def check_proposal_files_match_schema(self) -> list[AuditFinding]:
        """Validate each cr-*.yaml/json proposal against proposal.schema.json."""
        if not self.proposal_schema:
            return [
                AuditFinding(
                    AuditSeverity.ERROR,
                    "Proposal schema file could not be loaded.",
                    "Proposals: Schema Compliance",
                )
            ]

        paths = self._get_proposal_paths()
        if not paths:
            return [
                AuditFinding(
                    AuditSeverity.SUCCESS,
                    "No pending proposals found.",
                    "Proposals: Schema Compliance",
                )
            ]

        validator = jsonschema.Draft7Validator(self.proposal_schema)
        all_findings = []
        for path in paths:
            all_findings.extend(self._validate_single_proposal_schema(path, validator))
        return all_findings

    # CAPABILITY: audit.check.proposals_drift
    def check_signatures_match_content(self) -> list[AuditFinding]:
        """Detect content/signature drift for all pending proposals."""
        paths = self._get_proposal_paths()
        if not paths:
            return []

        all_findings = []
        for path in paths:
            all_findings.extend(self._validate_single_proposal_signatures(path))
        return all_findings

    # CAPABILITY: audit.check.proposals_list
    def list_pending_proposals(self) -> list[AuditFinding]:
        """Emit a friendly summary of pending proposals."""
        paths = self._get_proposal_paths()
        if not paths:
            if self.proposals_dir.exists():
                return [
                    AuditFinding(
                        AuditSeverity.SUCCESS,
                        "No pending proposals.",
                        "Proposals: Pending Summary",
                    )
                ]
            return []

        return [
            AuditFinding(
                AuditSeverity.WARNING,
                f"Pending proposal: {path.name}",
                "Proposals: Pending Summary",
                str(path.relative_to(self.context.repo_root)),
            )
            for path in paths
        ]
